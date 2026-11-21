import os
import threading
import time
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, SecretStr, StringConstraints

from agents import clarifier
from agents.graph import AgentLimits, AgentModels, build_graph
from agents.keys import KeyRejected, check_key
from agents.llm import create_llm
from agents.stub_llm import make_stub_models, stub_mode
from agents.usage import UsageMeter
from api.credits import CreditConfig, credit_store
from api.env import env_int
from api.events import log_event
from api.jobs import (
    FINISHED_STATUSES,
    JOB_FINISHED_HOOKS,
    TRIAL_FINISHED_HOOKS,
    cancel_job,
    create_job,
    get_job,
    has_capacity,
    public_view,
    screenshot_file,
    submit,
)
from api.limits import check_rate_limit, client_ip
from api.server_key import server_key_status
from api.trial import TrialConfig, TrialLedger, sweep_databases
from config import Settings, get_settings
from tools import edit_key
from tools.supabase import delete_database
from tools.vercel import get_project_env
from tools.workspace import new_job_id, sweep_build_output

router = APIRouter(prefix="/api")

# Used when the user's provider differs from the one configured for an agent.
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-6.1-sol"}

# Settings have no separate analyst entry; the analyst uses the guard settings.
SETTINGS_PREFIX = {
    "guard": "guard",
    "analyst": "guard",
    "architect": "architect",
    "test_planner": "test_planner",
    "builder": "builder",
    "validator": "validator",
}


# The longest description Vyskar takes, for a build and for its questions. A
# description goes to every agent, often more than once, so on free and bought
# builds a very long one would be paid for on Vyskar's own key.
MAX_PROMPT_CHARS = 4000

# A build needs something to build: blank or whitespace only is refused.
BuildPrompt = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PROMPT_CHARS)
]


class BuildRequest(BaseModel):
    prompt: BuildPrompt
    provider: Literal["anthropic", "openai"]
    api_key: SecretStr | None = None
    # To change an existing app instead of building a new one: its name, and
    # the edit key the browser got when the app was first built.
    app: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,49}$")
    edit_key: SecretStr | None = None
    # Answers to the questions from /api/clarify, added to the request.
    answers: list["Answer"] = Field(default_factory=list, max_length=clarifier.MAX_QUESTIONS)


class Answer(BaseModel):
    question: str = Field(max_length=300)
    answer: str = Field(max_length=200)


BuildRequest.model_rebuild()


CANNOT_CHANGE = "Vyskar can't change this app right now."
NOT_YOURS = "This app can only be changed from the browser that built it."
NOT_CHANGEABLE = (
    "This app was built before apps could be changed. Build it again to make it changeable."
)


def check_edit_key(app: str, key: SecretStr | None, read=get_project_env) -> None:
    """Allow a change only with the app's own edit key."""
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail=CANNOT_CHANGE)
    try:
        stored = read(token, app, edit_key.ENV_KEY)
    except Exception:
        raise HTTPException(status_code=503, detail=CANNOT_CHANGE) from None
    if stored is None:
        raise HTTPException(status_code=404, detail=NOT_CHANGEABLE)
    if key is None or not edit_key.matches(key.get_secret_value(), stored):
        raise HTTPException(status_code=403, detail=NOT_YOURS)


def make_models(provider: str, api_key: str, settings: Settings, meter=None) -> AgentModels:
    callbacks = [meter] if meter else None

    def llm(agent: str):
        prefix = SETTINGS_PREFIX[agent]
        if getattr(settings, f"{prefix}_provider") == provider:
            model = getattr(settings, f"{prefix}_model")
        else:
            model = DEFAULT_MODEL[provider]
        return create_llm(provider, model, api_key, callbacks)

    return AgentModels(**{agent: llm(agent) for agent in SETTINGS_PREFIX})


TRIAL_PROVIDER = "anthropic"
VISITOR_HEADER = "x-vyskar-visitor"
NO_KEY = "An API key is required."
TRIAL_USED_UP = "You have used your free builds. Add your own AI key to keep building."
TRIAL_PAUSED = "Free builds are paused right now. Add your own AI key to build."
OWN_KEYS_OFF = "Vyskar builds on its own AI now, no key needed."


def own_keys_allowed() -> bool:
    """Whether people may build with their own AI key. Off with ALLOW_OWN_KEYS=false."""
    return os.getenv("ALLOW_OWN_KEYS", "true").lower() != "false"


PAID_PAUSED = "Builds are paused for a moment. Your credits are safe; try again soon."


def log_paused(kind: str, reason: str, error: Exception | None = None) -> None:
    """Why a free or bought build was refused as paused, so `fly logs` says
    which to fix: key_missing (no ANTHROPIC_API_KEY on the server), rejected
    (the key is invalid or revoked) or no_credit (the Anthropic account is out
    of credit). The key itself is never logged."""
    cause = getattr(error, "__cause__", None) or error
    detail = str(cause)[:300] if cause else ""
    log_event("builds_paused", "", kind=kind, reason=reason, provider=TRIAL_PROVIDER, detail=detail)


_ledger: TrialLedger | None = None


def trial_ledger(settings: Settings) -> TrialLedger:
    """One ledger per process, on Fly's volume (DATA_DIR) so a deploy keeps
    the counts, else next to the workspaces. On first use it also starts
    recording the databases of finished trial apps."""
    global _ledger
    if _ledger is None:
        folder = os.getenv("DATA_DIR") or settings.workspaces_dir
        _ledger = TrialLedger(Path(folder) / "trial-usage.json")
        TRIAL_FINISHED_HOOKS.append(
            lambda job: _ledger.record_database(job.get("state", {}).get("database_name", ""))
        )
    return _ledger


def screenshots_dir(settings: Settings) -> Path | None:
    """Where photos of finished apps go: Fly's volume (DATA_DIR), else next to
    the workspaces. None, so no photos, with APP_SCREENSHOTS=false."""
    if os.getenv("APP_SCREENSHOTS", "true").lower() == "false":
        return None
    return Path(os.getenv("DATA_DIR") or settings.workspaces_dir) / "screenshots"


def _job_running(job_id: str) -> bool:
    job = get_job(job_id)
    return job is not None and job["status"] not in FINISHED_STATUSES


def _clean_finished_workspaces(job: dict) -> None:
    """After each build, delete the packages and outputs of every build that
    is over, this one included: they are rebuilt from source when needed, and
    otherwise fill the volume the credits database lives on."""
    workspace = (job.get("state") or {}).get("workspace_dir")
    if not workspace:
        return  # stopped before it had a folder: nothing new to clean
    # Job folders sit side by side in WORKSPACES_DIR (tools/workspace.py).
    cleaned = sweep_build_output(Path(workspace).parent, _job_running)
    if cleaned:
        log_event("workspaces_cleaned", job["job_id"], count=len(cleaned))


JOB_FINISHED_HOOKS.append(_clean_finished_workspaces)


def server_key(settings: Settings) -> str | None:
    """Vyskar's own key for free and bought builds, or None when unset."""
    try:
        return settings.api_key_for(TRIAL_PROVIDER)
    except ValueError:
        return None


def visitor_id(request: Request) -> str:
    return request.headers.get(VISITOR_HEADER, "").strip()[:64]


def _sweep_trial_databases(ledger: TrialLedger) -> None:
    token = os.environ.get("VERCEL_TOKEN")
    if token:
        sweep_databases(ledger, lambda name: delete_database(token, name))


def get_agent_limits(settings: Settings = Depends(get_settings)) -> AgentLimits:
    return AgentLimits(
        analyst_max_attempts=settings.analyst_max_attempts,
        architect_max_attempts=settings.architect_max_attempts,
        test_planner_max_attempts=settings.test_planner_max_attempts,
        builder_max_attempts=settings.builder_max_attempts,
        validator_max_attempts=settings.validator_max_attempts,
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/build", status_code=202)
def build(
    req: BuildRequest,
    request: Request,
    limits: AgentLimits = Depends(get_agent_limits),
    settings: Settings = Depends(get_settings),
):
    # Checked first: someone else's app is refused before any other work.
    if req.app:
        check_edit_key(req.app, req.edit_key)

    provider = req.provider
    trial = False
    paid = False
    ledger = None
    credits = CreditConfig.from_env()
    if stub_mode():
        key = ""  # canned answers, no model is called
    elif req.api_key and not own_keys_allowed():
        raise HTTPException(status_code=400, detail=OWN_KEYS_OFF)
    elif req.api_key:
        key = req.api_key.get_secret_value()
    elif os.environ.get("ALLOW_SERVER_KEYS") == "true":
        key = settings.api_key_for(req.provider)
    elif credits.enabled and credit_store(settings).balance(visitor_id(request)) > 0:
        # Bought builds run on Vyskar's own key, like free ones.
        try:
            key = settings.api_key_for(TRIAL_PROVIDER)
        except ValueError:
            server_key_status.record("key_missing")
            log_paused("paid", "key_missing")
            raise HTTPException(status_code=503, detail=PAID_PAUSED) from None
        provider, paid = TRIAL_PROVIDER, True
    else:
        config = TrialConfig.from_env()
        if not config.enabled:
            raise HTTPException(status_code=400, detail=NO_KEY)
        ledger = trial_ledger(settings)
        if ledger.builds_left(config, visitor_id(request), client_ip(request)) <= 0:
            raise HTTPException(status_code=400, detail=TRIAL_USED_UP)
        try:
            key = settings.api_key_for(TRIAL_PROVIDER)
        except ValueError:
            server_key_status.record("key_missing")
            log_paused("free", "key_missing")
            raise HTTPException(status_code=503, detail=TRIAL_PAUSED) from None
        provider, trial = TRIAL_PROVIDER, True

    # A bad key fails here in a second, instead of as an error mid build.
    if not stub_mode():
        try:
            check_key(provider, key)
            if trial or paid:
                server_key_status.record(None)
        except KeyRejected as error:
            if trial or paid:  # Vyskar's own key: not the visitor's problem to fix
                server_key_status.record(error.reason)
                log_paused("paid" if paid else "free", error.reason, error)
                raise HTTPException(
                    status_code=503, detail=PAID_PAUSED if paid else TRIAL_PAUSED
                ) from None
            raise HTTPException(status_code=400, detail=str(error)) from None

    if not has_capacity():
        raise HTTPException(
            status_code=503,
            detail="Vyskar is busy with other builds right now. Try again in a few minutes.",
            headers={"Retry-After": "300"},
        )

    # After the key check, so a request without a key does not use up an attempt.
    check_rate_limit(request)

    meter = UsageMeter()
    if stub_mode():
        models = AgentModels(**make_stub_models(SETTINGS_PREFIX))
    else:
        models = make_models(provider, key, settings, meter)
    graph = build_graph(
        models,
        limits,
        settings.workspaces_dir,
        vercel_token=os.environ.get("VERCEL_TOKEN"),
        builder_mode=settings.builder_mode,
        supabase_config_id=os.environ.get("VERCEL_SUPABASE_CONFIG_ID"),
        supabase_access_token=os.environ.get("SUPABASE_ACCESS_TOKEN"),
        screenshots_dir=screenshots_dir(settings),
    )
    job_id = new_job_id()
    # A credit is spent only once the build is sure to start.
    if paid and not credit_store(settings).use(visitor_id(request), job_id):
        raise HTTPException(status_code=400, detail=NO_KEY)
    # Checked again and counted in one step: the check above came before the
    # key check, so two requests at once could both have passed it.
    if trial and not ledger.claim_build(config, visitor_id(request), client_ip(request)):
        raise HTTPException(status_code=400, detail=TRIAL_USED_UP)
    prompt = clarifier.with_answers(req.prompt, [a.model_dump() for a in req.answers])
    create_job(job_id, prompt, settings.builder_mode, trial=trial, meter=meter)
    if req.app:
        extra, new_key = {"app_name": req.app}, None
    else:
        new_key = edit_key.new_key()
        extra = {"edit_key_hash": edit_key.hash_key(new_key)}
    submit(graph, job_id, prompt, settings.graph_recursion_limit, extra)
    if ledger is not None:
        # Old trial databases go now, so their slots are free for new apps.
        threading.Thread(target=_sweep_trial_databases, args=(ledger,), daemon=True).start()
    # The only time the key is sent: the browser keeps it to change the app later.
    return {"job_id": job_id, "edit_key": new_key}


@router.get("/trial")
def trial_status(request: Request, settings: Settings = Depends(get_settings)):
    """Whether free builds are on, and how many this visitor has left."""
    config = TrialConfig.from_env()
    ledger = trial_ledger(settings)
    visitor = visitor_id(request)
    left = ledger.builds_left(config, visitor, client_ip(request))
    # Only worth checking Vyskar's key when this visitor could use it.
    paused = (
        config.enabled
        and left > 0
        and not stub_mode()
        and server_key_status.paused_reason(TRIAL_PROVIDER, server_key(settings)) is not None
    )
    bonus_builds = env_int("FEEDBACK_BONUS_BUILDS", 2)
    return {
        "enabled": config.enabled,
        "builds_left": left,
        # Free builds are on but Vyskar's own key doesn't work: the app says
        # so before Build is tapped, instead of offering a build it would refuse.
        "paused": paused,
        "own_keys": own_keys_allowed(),
        # Feedback earns more builds once; the app offers it when none are left.
        # FEEDBACK_BONUS_BUILDS=0 turns the offer off.
        "bonus_available": config.enabled and bonus_builds > 0 and not ledger.bonus_used(visitor),
        "bonus_builds": bonus_builds,
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return public_view(job)


@router.get("/jobs/{job_id}/screenshot")
def get_job_screenshot(job_id: str):
    """The photo of a finished build's live app, for the end of its animation."""
    job = get_job(job_id)
    path = screenshot_file(job) if job and job["status"] == "succeeded" else None
    if path is None:
        raise HTTPException(status_code=404, detail="no screenshot")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_build(job_id: str):
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not cancel_job(job_id):
        raise HTTPException(status_code=409, detail="This build has already finished.")
    return public_view(get_job(job_id))


class ClarifyRequest(BaseModel):
    prompt: str = Field(max_length=MAX_PROMPT_CHARS)
    provider: Literal["anthropic", "openai"]
    api_key: SecretStr | None = None
    app: str | None = None


CLARIFY_PER_HOUR = 30
_clarify_hits: dict[str, list[float]] = {}
_clarify_lock = threading.Lock()


def _clarify_allowed(ip: str) -> bool:
    now = time.monotonic()
    with _clarify_lock:
        hits = [t for t in _clarify_hits.get(ip, []) if now - t < 3600]
        allowed = len(hits) < CLARIFY_PER_HOUR
        if allowed:
            hits.append(now)
        _clarify_hits[ip] = hits
        return allowed


@router.post("/clarify")
def clarify(req: ClarifyRequest, request: Request, settings: Settings = Depends(get_settings)):
    """Up to two questions before building, only when they matter. Uses no
    build. Any problem means no questions, so it never stands in the way."""
    none = {"questions": []}
    if stub_mode() or req.app or not req.prompt.strip():
        return none  # changes to an app go straight to building
    provider = req.provider
    try:
        if req.api_key and own_keys_allowed():
            key = req.api_key.get_secret_value()
        elif os.environ.get("ALLOW_SERVER_KEYS") == "true":
            key = settings.api_key_for(provider)
        else:
            visitor, ip = visitor_id(request), client_ip(request)
            credits = CreditConfig.from_env()
            paid = credits.enabled and credit_store(settings).balance(visitor) > 0
            free = trial_ledger(settings).builds_left(TrialConfig.from_env(), visitor, ip) > 0
            if not (paid or free):
                return none
            provider, key = TRIAL_PROVIDER, settings.api_key_for(TRIAL_PROVIDER)
    except Exception:
        return none
    if not _clarify_allowed(client_ip(request)):
        return none
    if settings.guard_provider == provider:
        model = settings.guard_model
    else:
        model = DEFAULT_MODEL[provider]
    return {"questions": clarifier.ask(create_llm(provider, model, key), req.prompt)}
