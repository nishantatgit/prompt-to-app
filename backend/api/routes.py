import os
import threading
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.keys import KeyRejected, check_key
from agents.llm import create_llm
from agents.stub_llm import make_stub_models, stub_mode
from agents.usage import UsageMeter
from api.jobs import (
    TRIAL_FINISHED_HOOKS,
    cancel_job,
    create_job,
    get_job,
    has_capacity,
    public_view,
    submit,
)
from api.credits import CreditConfig, credit_store
from api.limits import check_rate_limit, client_ip
from api.trial import TrialConfig, TrialLedger, sweep_databases
from config import Settings, get_settings
from tools import edit_key
from tools.supabase import delete_database
from tools.vercel import get_project_env
from tools.workspace import new_job_id

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


class BuildRequest(BaseModel):
    prompt: str
    provider: Literal["anthropic", "openai"]
    api_key: SecretStr | None = None
    # To change an existing app instead of building a new one: its name, and
    # the edit key the browser got when the app was first built.
    app: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,49}$")
    edit_key: SecretStr | None = None


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
PAID_PAUSED = "Builds are paused for a moment. Your credits are safe; try again soon."

_ledger: TrialLedger | None = None


def trial_ledger(settings: Settings) -> TrialLedger:
    """One ledger per process, kept next to the workspaces. On first use it
    also starts recording the databases of finished trial apps."""
    global _ledger
    if _ledger is None:
        _ledger = TrialLedger(Path(settings.workspaces_dir) / "trial-usage.json")
        TRIAL_FINISHED_HOOKS.append(
            lambda job: _ledger.record_database(job.get("state", {}).get("database_name", ""))
        )
    return _ledger


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
    elif req.api_key:
        key = req.api_key.get_secret_value()
    elif os.environ.get("ALLOW_SERVER_KEYS") == "true":
        key = settings.api_key_for(req.provider)
    elif credits.enabled and credit_store(settings).balance(visitor_id(request)) > 0:
        # Bought builds run on Vyskar's own key, like free ones.
        try:
            key = settings.api_key_for(TRIAL_PROVIDER)
        except ValueError:
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
            raise HTTPException(status_code=503, detail=TRIAL_PAUSED) from None
        provider, trial = TRIAL_PROVIDER, True

    # A bad key fails here in a second, instead of as an error mid build.
    if not stub_mode():
        try:
            check_key(provider, key)
        except KeyRejected as error:
            if trial or paid:  # Vyskar's own key: not the visitor's problem to fix
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
    )
    job_id = new_job_id()
    # A credit is spent only once the build is sure to start.
    if paid and not credit_store(settings).use(visitor_id(request), job_id):
        raise HTTPException(status_code=400, detail=NO_KEY)
    create_job(job_id, req.prompt, settings.builder_mode, trial=trial, meter=meter)
    if trial:
        ledger.record_build(visitor_id(request), client_ip(request))
    if req.app:
        extra, new_key = {"app_name": req.app}, None
    else:
        new_key = edit_key.new_key()
        extra = {"edit_key_hash": edit_key.hash_key(new_key)}
    submit(graph, job_id, req.prompt, settings.graph_recursion_limit, extra)
    if ledger is not None:
        # Old trial databases go now, so their slots are free for new apps.
        threading.Thread(target=_sweep_trial_databases, args=(ledger,), daemon=True).start()
    # The only time the key is sent: the browser keeps it to change the app later.
    return {"job_id": job_id, "edit_key": new_key}


@router.get("/trial")
def trial_status(request: Request, settings: Settings = Depends(get_settings)):
    """Whether free builds are on, and how many this visitor has left."""
    config = TrialConfig.from_env()
    left = trial_ledger(settings).builds_left(config, visitor_id(request), client_ip(request))
    return {"enabled": config.enabled, "builds_left": left}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return public_view(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_build(job_id: str):
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not cancel_job(job_id):
        raise HTTPException(status_code=409, detail="This build has already finished.")
    return public_view(get_job(job_id))
