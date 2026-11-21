import time

from api import jobs


def _finish(job_id: str, hours_ago: float, status: str = "succeeded") -> None:
    with jobs._lock:
        jobs._jobs[job_id].update(status=status, finished_at=time.time() - hours_ago * 3600)


def test_a_job_finished_long_ago_is_forgotten_when_the_next_starts(monkeypatch):
    monkeypatch.setattr(jobs, "FINISHED_JOB_HOURS", 24)
    jobs.create_job("old-1", "a timer")
    _finish("old-1", hours_ago=25)
    jobs.create_job("old-2", "a timer")
    _finish("old-2", hours_ago=25, status="cancelled")

    jobs.create_job("new-1", "a notes app")

    assert jobs.get_job("old-1") is None
    assert jobs.get_job("old-2") is None
    assert jobs.get_job("new-1")["status"] == "queued"


def test_recent_and_unfinished_jobs_are_kept(monkeypatch):
    monkeypatch.setattr(jobs, "FINISHED_JOB_HOURS", 24)
    jobs.create_job("recent-1", "a timer")
    _finish("recent-1", hours_ago=2, status="failed")
    jobs.create_job("running-1", "a timer")
    with jobs._lock:
        # Running for days: never dropped, however old.
        jobs._jobs["running-1"].update(status="running", created_at=time.time() - 72 * 3600)
    jobs.create_job("done-no-clock", "a timer")
    with jobs._lock:
        # Finished but its clock not stopped yet: the run is still wrapping up.
        jobs._jobs["done-no-clock"].update(status="succeeded")

    jobs.create_job("new-2", "a notes app")

    assert jobs.get_job("recent-1")["status"] == "failed"
    assert jobs.get_job("running-1")["status"] == "running"
    assert jobs.get_job("done-no-clock")["status"] == "succeeded"


def test_a_cancelled_build_still_running_when_forgotten_does_not_crash(monkeypatch):
    monkeypatch.setattr(jobs, "FINISHED_JOB_HOURS", 1)
    jobs.create_job("slow-cancel", "a timer")
    jobs.cancel_job("slow-cancel")
    _finish("slow-cancel", hours_ago=2, status="cancelled")
    jobs.create_job("new-3", "a notes app")
    assert jobs.get_job("slow-cancel") is None

    jobs._finish_clock("slow-cancel")  # the run's last step, long after


def test_a_mistyped_setting_falls_back_to_a_day(monkeypatch):
    monkeypatch.setenv("FINISHED_JOB_HOURS", "a day")
    assert jobs.env_int("FINISHED_JOB_HOURS", 24, minimum=1) == 24
    monkeypatch.setenv("FINISHED_JOB_HOURS", "0")
    assert jobs.env_int("FINISHED_JOB_HOURS", 24, minimum=1) == 24
