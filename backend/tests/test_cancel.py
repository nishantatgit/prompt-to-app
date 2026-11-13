from typing import TypedDict

from fastapi.testclient import TestClient
from langgraph.graph import END, START, StateGraph

from agents.build_loop import make_build_loop
from api import jobs
from tests.test_build_loop import ScriptedBuild, ScriptedModel, done, state, tool  # noqa: F401


class FakeGraph:
    """Yields the given chunks; `during` runs after the first one, standing in
    for the user pressing Cancel while the build runs."""

    def __init__(self, chunks, during=None):
        self.chunks = chunks
        self.during = during
        self.config = None

    def stream(self, state, config, stream_mode):
        self.config = config
        for i, chunk in enumerate(self.chunks):
            yield chunk
            if i == 0 and self.during:
                self.during()


CHUNKS = [
    ("updates", {"guard": {"allowed": True}}),
    ("updates", {"analyst": {"requirements": {"app_summary": "x"}}}),
    ("updates", {"deploy": {"deploy_url": "https://x.vyskar.app"}}),
]


def test_a_running_job_can_be_cancelled_once():
    jobs.create_job("c-1", "a timer")
    assert jobs.cancel_job("c-1") is True
    job = jobs.get_job("c-1")
    assert job["status"] == "cancelled"
    assert job["reason"] == jobs.CANCELLED_REASON
    assert jobs.cancel_job("c-1") is False


def test_cancelling_mid_build_stops_the_graph_and_keeps_the_status():
    jobs.create_job("c-2", "a timer")
    graph = FakeGraph(CHUNKS, during=lambda: jobs.cancel_job("c-2"))
    jobs._run(graph, "c-2", "a timer", 50)

    job = jobs.get_job("c-2")
    assert job["status"] == "cancelled"
    assert job["stage"] == "checking request"  # stopped after the first step
    assert jobs.public_view(job)["deploy_url"] == ""


def test_a_job_cancelled_in_the_queue_never_starts():
    jobs.create_job("c-3", "a timer")
    jobs.cancel_job("c-3")
    graph = FakeGraph(CHUNKS)
    jobs._run(graph, "c-3", "a timer", 50)
    assert graph.config is None
    assert jobs.get_job("c-3")["status"] == "cancelled"


def test_finished_jobs_cannot_be_cancelled():
    jobs.create_job("c-4", "a timer")
    jobs._run(FakeGraph(CHUNKS), "c-4", "a timer", 50)
    assert jobs.get_job("c-4")["status"] == "succeeded"
    assert jobs.cancel_job("c-4") is False


def test_cancelled_jobs_free_their_place():
    jobs.create_job("c-5", "a timer")
    before = jobs.active_job_count()
    jobs.cancel_job("c-5")
    assert jobs.active_job_count() == before - 1


class LoopState(TypedDict, total=False):
    workspace_dir: str
    architecture: dict
    build_ok: bool
    build_log: str
    files_written: list
    builder_attempts: int
    loop_turns: int


def run_loop_in_graph(state, model, build, cancelled):
    graph = StateGraph(LoopState)
    graph.add_node("builder", make_build_loop(model, build=build))
    graph.add_edge(START, "builder")
    graph.add_edge("builder", END)
    return graph.compile().invoke(state, {"configurable": {"cancelled": cancelled}})


def test_the_build_loop_stops_before_its_next_model_call(state):  # noqa: F811
    presses = iter([False, True])  # Cancel pressed after the first turn
    model = ScriptedModel([tool("list_files"), done()])
    out = run_loop_in_graph(state, model, ScriptedBuild((True, "")), lambda: next(presses))

    assert len(model.calls) == 1
    assert out["build_ok"] is False
    assert out["build_log"] == "Cancelled by the user."


def test_cancel_endpoint():
    from api.main import app

    client = TestClient(app)
    assert client.post("/api/jobs/nope/cancel").status_code == 404

    jobs.create_job("c-6", "a timer")
    response = client.post("/api/jobs/c-6/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert client.post("/api/jobs/c-6/cancel").status_code == 409
