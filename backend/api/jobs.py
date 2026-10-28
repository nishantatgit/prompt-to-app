import threading
import time
from concurrent.futures import ThreadPoolExecutor

MAX_CONCURRENT_JOBS = 2

_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

STAGES = {
    "guard": "checking request",
    "analyst": "requirements",
    "architect": "architecture",
    "setup_workspace": "setting up",
    "builder": "building",
    "build_check": "building",
    "build_done": "building",
    "test_planner": "planning tests",
    "write_test": "planning tests",
    "test_executor": "testing",
    "deploy": "deploying",
}


def create_job(job_id: str, prompt: str) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "queued",
            "stage": None,
            "reason": "",
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


def _outcome(state: dict) -> tuple[str, str]:
    if state.get("allowed") is False:
        return "rejected", state.get("guard_reason", "")
    if state.get("deploy_url"):
        return "succeeded", ""
    reason = (
        state.get("deploy_error")
        or state.get("gate_reason")
        or "; ".join(state.get("errors") or [])
        or ("build failed" if state.get("build_ok") is False else "stopped early")
    )
    return "failed", reason


def _run(graph, job_id: str, prompt: str, recursion_limit: int) -> None:
    _update(job_id, status="running")
    state = {"prompt": prompt, "job_id": job_id}
    try:
        for update in graph.stream(
            dict(state), {"recursion_limit": recursion_limit}, stream_mode="updates"
        ):
            for node, values in update.items():
                state.update(values or {})
                _update(job_id, stage=STAGES.get(node, node), state=dict(state))
        status, reason = _outcome(state)
        _update(job_id, status=status, reason=reason, state=state)
    except Exception as error:
        _update(job_id, status="failed", reason=f"internal error: {error}")


def submit(graph, job_id: str, prompt: str, recursion_limit: int) -> None:
    _executor.submit(_run, graph, job_id, prompt, recursion_limit)


def public_view(job: dict) -> dict:
    state = job["state"]
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "reason": job["reason"],
        "deploy_url": state.get("deploy_url", ""),
        "gate_reason": state.get("gate_reason", ""),
        "test_summary": state.get("test_summary", ""),
    }
