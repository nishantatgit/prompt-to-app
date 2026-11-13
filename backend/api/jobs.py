import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor

from agents.keys import user_error_reason

MAX_CONCURRENT_JOBS = 2

_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

STAGES = {
    "guard": "checking request",
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
    "deploy": "deploying",
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


def create_job(job_id: str, prompt: str, builder_mode: str = "pipeline") -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "queued",
            "stage": None,
            "reason": "",
            "builder_mode": builder_mode,
            "activity": [],
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
        job.update(status="cancelled", reason=CANCELLED_REASON)
        return True


def is_cancelled(job_id: str) -> bool:
    with _lock:
        return _jobs[job_id]["status"] == "cancelled"


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


def _run(graph, job_id: str, prompt: str, recursion_limit: int) -> None:
    if is_cancelled(job_id):
        return  # cancelled while waiting in the queue
    _update(job_id, status="running")
    state = {"prompt": prompt, "job_id": job_id}
    config = {
        "recursion_limit": recursion_limit,
        # Long steps, such as the build loop, check this between model calls.
        "configurable": {"cancelled": lambda: is_cancelled(job_id)},
    }
    try:
        for mode, chunk in graph.stream(dict(state), config, stream_mode=["updates", "custom"]):
            if is_cancelled(job_id):
                return
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


def submit(graph, job_id: str, prompt: str, recursion_limit: int) -> None:
    _executor.submit(_run, graph, job_id, prompt, recursion_limit)


def public_view(job: dict) -> dict:
    state = job["state"]
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "reason": job["reason"],
        "builder_mode": job.get("builder_mode", "pipeline"),
        "activity": job.get("activity", []),
        "deploy_url": state.get("deploy_url", ""),
        "database_name": state.get("database_name", ""),
        "confidence": state.get("confidence"),
        "test_summary": state.get("test_summary", ""),
    }
