import json

from api import jobs
from api.events import log_event
from tests.test_step_timings import Clock, TimedGraph, finished, started


def events(out: str) -> list[dict]:
    """The JSON event lines in captured stdout, skipping any other output."""
    lines = [line for line in out.splitlines() if line.startswith("{")]
    return [json.loads(line) for line in lines]


def test_a_build_logs_start_stages_and_finish_as_json(monkeypatch, capsys):
    clock = Clock()
    monkeypatch.setattr(jobs.time, "time", clock)
    jobs.create_job("ev-1", "A secret plan for my notes app")
    graph = TimedGraph(
        clock,
        [
            (0, started("guard")),
            (2, finished("guard")),
            (0, ("updates", {"guard": {"allowed": True}})),
            (0, started("builder")),
            (0, started("build_check")),  # same stage: no second stage line
            (10, finished("build_check")),
            (5, finished("builder")),
            (0, started("deploy")),
            (8, finished("deploy")),
            (0, ("updates", {"deploy": {"deploy_url": "https://x.vyskar.app"}})),
        ],
    )
    jobs._run(graph, "ev-1", "A secret plan for my notes app", 50)

    logged = events(capsys.readouterr().out)
    assert [e["event"] for e in logged] == [
        "build_start",
        "build_stage",
        "build_stage",
        "build_stage",
        "build_finish",
    ]
    assert all(e["job_id"] == "ev-1" and "ts" in e for e in logged)

    start = logged[0]
    assert start["builder_mode"] == "pipeline" and start["trial"] is False
    assert start["change"] is False and start["prompt_chars"] == 30
    assert [e["stage"] for e in logged[1:4]] == ["checking request", "building", "deploying"]

    finish = logged[-1]
    assert finish["status"] == "succeeded" and finish["reason"] == ""
    assert finish["seconds"] == 25.0
    assert finish["stages"] == {"checking request": 2.0, "building": 15.0, "deploying": 8.0}
    assert finish["deploy_url"] == "https://x.vyskar.app"


def test_the_prompt_is_never_logged(capsys):
    jobs.create_job("ev-2", "my private idea")
    graph = TimedGraph(Clock(), [(0, ("updates", {"guard": {"allowed": False}}))])
    jobs._run(graph, "ev-2", "my private idea", 50)
    assert "my private idea" not in capsys.readouterr().out


def test_a_failed_build_logs_a_short_reason(capsys):
    class Broken:
        def stream(self, state, config, stream_mode):
            raise RuntimeError("x" * 1000)
            yield  # pragma: no cover

    jobs.create_job("ev-3", "p", builder_mode="loop", trial=True)
    jobs._run(Broken(), "ev-3", "p", 50, {"app_name": "notes"})

    logged = events(capsys.readouterr().out)
    start, finish = logged[0], logged[-1]
    assert start["change"] is True and start["builder_mode"] == "loop" and start["trial"] is True
    assert start["paid"] is False and finish["paid"] is False
    assert finish["event"] == "build_finish" and finish["status"] == "failed"
    assert len(finish["reason"]) == jobs.MAX_LOGGED_REASON


def test_a_build_cancelled_in_the_queue_logs_only_its_finish(capsys):
    jobs.create_job("ev-4", "p")
    jobs.cancel_job("ev-4")
    jobs._run(TimedGraph(Clock(), []), "ev-4", "p", 50)
    logged = events(capsys.readouterr().out)
    assert [e["event"] for e in logged] == ["build_finish"]
    assert logged[0]["status"] == "cancelled"


def test_a_field_that_cannot_be_written_still_gives_a_line(capsys):
    log_event("build_stage", "ev-5", stage=float("nan"), bad={1, 2})
    record = json.loads(capsys.readouterr().out)
    assert record["event"] == "build_stage" and record["job_id"] == "ev-5"
