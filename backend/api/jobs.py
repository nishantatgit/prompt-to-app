import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agents.keys import user_error_reason
from api.events import log_event

MAX_CONCURRENT_JOBS = 2

_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

STAGES = {
    "guard": "checking request",
    "load_app": "checking request",
    "analyst": "requirements",
    "architect": "architecture",
    "setup_workspace": "setting up",
    "database": "setting up",
    "builder": "building",
    "build_check": "building",
    "build_done": "building",
    "migrations": "building",
    "test_planner": "planning tests",
    "write_test": "planning tests",
    "test_executor": "testing",
    "save_spec": "deploying",
    "deploy": "deploying",
    "screenshot": "deploying",
}

# The job view shows the build loop's latest steps; older ones are dropped.
MAX_ACTIVITY = 50

MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "6"))
FINISHED_STATUSES = {"succeeded", "failed", "rejected", "cancelled"}
CANCELLED_REASON = "You cancelled this build."


def active_job_count() -> int:
    with _lock:
        return sum(1 for job in _jobs.values() if job["status"] not in FINISHED_STATUSES)


def has_capacity() -> bool:
    return active_job_count() < MAX_ACTIVE_JOBS


# Called with each finished job that ran on the free trial, such as to
# schedule its database for deletion.
TRIAL_FINISHED_HOOKS: list = []

# Called with every finished job, whatever paid for it, such as to push a
# notification to the browser that started it.
JOB_FINISHED_HOOKS: list = []


def create_job(
    job_id: str, prompt: str, builder_mode: str = "pipeline", trial: bool = False, meter=None
) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "queued",
            "stage": None,
            "reason": "",
            "builder_mode": builder_mode,
            "trial": trial,
            "meter": meter,  # a UsageMeter: the build's tokens and cost
            "activity": [],
            # Per stage: when its first step started, how many of its steps
            # are running, and when its last step finished.
            "timings": {},
            "started_at": None,
            "finished_at": None,
            "created_at": time.time(),
            "state": {},
        }


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update(job_id: str, **fields) -> None:
    with _lock:
        _jobs[job_id].update(fields)


def _add_activity(job_id: str, text: str) -> None:
    """One step of the build loop. The loop runs while the job is building."""
    with _lock:
        job = _jobs[job_id]
        job["activity"] = (job["activity"] + [text])[-MAX_ACTIVITY:]
        job["stage"] = "building"


def cancel_job(job_id: str) -> bool:
    """Stop a build. Returns False when the job has already finished.

    The job shows as cancelled at once. The graph stops at the next step,
    and the build loop at its next turn, so no more model calls are made
    with the user's key."""
    with _lock:
        job = _jobs[job_id]
        if job["status"] in FINISHED_STATUSES:
            return False
        job.update(status="cancelled", reason=CANCELLED_REASON, finished_at=time.time())
        return True


def is_cancelled(job_id: str) -> bool:
    with _lock:
        return _jobs[job_id]["status"] == "cancelled"


def _step_started(job_id: str, node: str) -> None:
    stage = STAGES.get(node)
    if stage is None:
        return
    with _lock:
        timings = _jobs[job_id]["timings"]
        first = stage not in timings
        timing = timings.setdefault(stage, {"started": time.time(), "running": 0})
        timing["running"] += 1
        timing["finished"] = None
    if first:
        log_event("build_stage", job_id, stage=stage, node=node)


def _step_finished(job_id: str, node: str) -> None:
    stage = STAGES.get(node)
    if stage is None:
        return
    with _lock:
        timing = _jobs[job_id]["timings"].get(stage)
        if timing is None:
            return
        timing["running"] = max(0, timing["running"] - 1)
        if timing["running"] == 0:
            timing["finished"] = time.time()


def _finish_clock(job_id: str) -> None:
    """Stop the job's clock, and any stage still running when it ended."""
    now = time.time()
    with _lock:
        job = _jobs[job_id]
        job["finished_at"] = job["finished_at"] or now
        for timing in job["timings"].values():
            if timing.get("finished") is None:
                timing["finished"] = now
                timing["running"] = 0


def timings_view(job: dict, now: float | None = None) -> dict:
    """Seconds per stage, and in total, counting running ones up to now."""
    now = now or time.time()
    stages = {
        stage: {
            "seconds": round((t.get("finished") or now) - t["started"], 1),
            "running": t.get("finished") is None,
        }
        for stage, t in job.get("timings", {}).items()
    }
    started = job.get("started_at")
    total = round((job.get("finished_at") or now) - started, 1) if started else None
    return {"stages": stages, "total_seconds": total}


def _outcome(state: dict) -> tuple[str, str]:
    if state.get("allowed") is False:
        return "rejected", state.get("guard_reason", "")
    if state.get("deploy_url"):
        return "succeeded", ""
    reason = (
        state.get("deploy_error")
        or state.get("database_error")
        or "; ".join(state.get("errors") or [])
        or ("build failed" if state.get("build_ok") is False else "stopped early")
    )
    return "failed", reason


# Long failure reasons, such as a build log, are cut to keep log lines small.
MAX_LOGGED_REASON = 300


def _log_finish(job: dict) -> None:
    """One build_finish line per build: how it ended and where time went."""
    timings = timings_view(job)
    log_event(
        "build_finish",
        job["job_id"],
        status=job["status"],
        reason=(job.get("reason") or "")[:MAX_LOGGED_REASON],
        builder_mode=job.get("builder_mode", "pipeline"),
        trial=job.get("trial", False),
        seconds=timings["total_seconds"],
        stages={stage: t["seconds"] for stage, t in timings["stages"].items()},
        deploy_url=(job.get("state") or {}).get("deploy_url", ""),
    )


def _log_usage(job: dict) -> None:
    """One build_cost line per build, to price builds from real runs."""
    meter = job.get("meter")
    if meter is None:
        return
    usage = meter.summary()
    if not usage["calls"]:
        return
    record = {
        "status": job["status"],
        "trial": job.get("trial", False),
        "seconds": timings_view(job)["total_seconds"],
        "cost_usd": usage["cost_usd"],
        "calls": usage["calls"],
        "input_tokens": usage["input_tokens"],
        "cache_read_tokens": usage["cache_read_tokens"],
        "output_tokens": usage["output_tokens"],
    }
    log_event("build_cost", job["job_id"], **record)


def _run(graph, job_id: str, prompt: str, recursion_limit: int, extra: dict | None = None) -> None:
    try:
        _run_graph(graph, job_id, prompt, recursion_limit, extra)
    finally:
        _finish_clock(job_id)
        job = get_job(job_id)
        if job:
            _log_finish(job)
            _log_usage(job)
        if job and job.get("trial"):
            for hook in TRIAL_FINISHED_HOOKS:
                try:
                    hook(job)
                except Exception:
                    pass
        if job:
            for hook in JOB_FINISHED_HOOKS:
                try:
                    hook(job)
                except Exception:
                    pass


def _run_graph(
    graph, job_id: str, prompt: str, recursion_limit: int, extra: dict | None = None
) -> None:
    if is_cancelled(job_id):
        return  # cancelled while waiting in the queue
    _update(job_id, status="running", started_at=time.time())
    job = get_job(job_id) or {}
    log_event(
        "build_start",
        job_id,
        builder_mode=job.get("builder_mode", "pipeline"),
        trial=job.get("trial", False),
        change=bool((extra or {}).get("app_name")),
        prompt_chars=len(prompt),
    )
    state = {**(extra or {}), "prompt": prompt, "job_id": job_id}
    config = {
        "recursion_limit": recursion_limit,
        # Long steps, such as the build loop, check this between model calls.
        "configurable": {"cancelled": lambda: is_cancelled(job_id)},
    }
    try:
        stream = graph.stream(dict(state), config, stream_mode=["updates", "custom", "tasks"])
        for mode, chunk in stream:
            if is_cancelled(job_id):
                return
            if mode == "tasks":
                # A task event without a result is the step starting.
                if "result" in chunk or "error" in chunk:
                    _step_finished(job_id, chunk["name"])
                else:
                    _step_started(job_id, chunk["name"])
                continue
            if mode == "custom":
                if "activity" in chunk:
                    _add_activity(job_id, chunk["activity"])
                continue
            for node, values in chunk.items():
                state.update(values or {})
                _update(job_id, stage=STAGES.get(node, node), state=dict(state))
        status, reason = _outcome(state)
        with _lock:
            if _jobs[job_id]["status"] != "cancelled":
                _jobs[job_id].update(status=status, reason=reason, state=state)
    except Exception as error:
        if is_cancelled(job_id):
            return
        reason = user_error_reason(error) or f"internal error: {error}"
        _update(job_id, status="failed", reason=reason)


def submit(
    graph, job_id: str, prompt: str, recursion_limit: int, extra: dict | None = None
) -> None:
    """extra: more starting state, such as the app to change."""
    _executor.submit(_run, graph, job_id, prompt, recursion_limit, extra)


def public_view(job: dict) -> dict:
    state = job["state"]
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "reason": job["reason"],
        "builder_mode": job.get("builder_mode", "pipeline"),
        "trial": job.get("trial", False),
        "activity": job.get("activity", []),
        "deploy_url": state.get("deploy_url", ""),
        "app_name": state.get("deployed_name") or state.get("app_name", ""),
        "editable": bool(state.get("editable")),
        "database_name": state.get("database_name", ""),
        "confidence": state.get("confidence"),
        "test_summary": state.get("test_summary", ""),
        "timings": timings_view(job),
        "usage": job["meter"].summary() if job.get("meter") else None,
        # Shown once the build has succeeded, so the photo never appears early.
        "screenshot_url": (
            f"/api/jobs/{job['job_id']}/screenshot"
            if job["status"] == "succeeded" and screenshot_file(job)
            else ""
        ),
    }


def screenshot_file(job: dict) -> Path | None:
    """The photo of the job's live app, when one was taken."""
    path = job["state"].get("screenshot_path")
    if path and Path(path).is_file():
        return Path(path)
    return None
