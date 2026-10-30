from typing import TypedDict


class JobState(TypedDict, total=False):
    prompt: str

    job_id: str
    workspace_dir: str | None
    allowed: bool
    guard_category: str
    guard_reason: str

    requirements: dict | None
    analyst_attempts: int
    analyst_feedback: str

    architecture: dict | None
    architect_attempts: int
    architect_feedback: str

    test_plan: dict | None
    test_planner_attempts: int
    test_planner_feedback: str
    files_written: list[str]

    builder_attempts: int
    build_ok: bool
    build_log: str

    tests_ok: bool
    test_summary: str
    test_report_path: str

    confidence: float

    deploy_url: str
    deploy_error: str

    errors: list[str]
