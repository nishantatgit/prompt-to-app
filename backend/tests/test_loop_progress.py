from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.build_loop import describe, make_build_loop
from api import jobs
from tests.test_build_loop import ScriptedBuild, ScriptedModel, done, state, tool  # noqa: F401


def test_tool_calls_are_described_in_plain_words():
    assert describe({"name": "write_file", "args": {"path": "src/App.jsx"}}) == "Writing src/App.jsx"
    assert describe({"name": "edit_file", "args": {"path": "src/index.css"}}) == "Editing src/index.css"
    assert describe({"name": "list_files", "args": {}}) == "Looking at the project files"
    assert describe({"name": "something_new", "args": {}}) == "Using something_new"


class LoopState(TypedDict, total=False):
    workspace_dir: str
    architecture: dict
    build_ok: bool
    build_log: str
    files_written: list
    builder_attempts: int
    loop_turns: int


def stream_activity(state, model, build):
    """Run the loop as a graph node and collect what it reports."""
    graph = StateGraph(LoopState)
    graph.add_node("builder", make_build_loop(model, build=build))
    graph.add_edge(START, "builder")
    graph.add_edge("builder", END)
    events = graph.compile().stream(state, stream_mode="custom")
    return [event["activity"] for event in events]


def test_the_loop_reports_each_step_while_it_runs(state):  # noqa: F811
    model = ScriptedModel(
        [
            tool("write_file", path="src/App.jsx", content="broken"),
            done(),
            tool("edit_file", path="src/App.jsx", old="broken", new="fixed"),
            done(),
        ]
    )
    build = ScriptedBuild((False, "error"), (True, "built"))

    assert stream_activity(state, model, build) == [
        "Writing src/App.jsx",
        "Running build 1 of 3",
        "Build 1 failed, fixing it",
        "Editing src/App.jsx",
        "Running build 2 of 3",
        "Build passed",
    ]


def test_the_loop_reports_nothing_outside_a_graph(state):  # noqa: F811
    out = make_build_loop(ScriptedModel([done()]), build=ScriptedBuild((True, "")))(state)
    assert out["build_ok"] is True


class FakeGraph:
    def __init__(self, chunks):
        self.chunks = chunks

    def stream(self, state, config, stream_mode):
        assert stream_mode == ["updates", "custom"]
        yield from self.chunks


def test_jobs_keep_the_activity_and_show_it_with_the_mode():
    jobs.create_job("job-1", "a timer", "loop")
    graph = FakeGraph(
        [
            ("updates", {"setup_workspace": {"workspace_dir": "/tmp/x"}}),
            ("custom", {"activity": "Writing src/App.jsx"}),
            ("custom", {"activity": "Build passed"}),
            ("updates", {"deploy": {"deploy_url": "https://x.vyskar.app"}}),
        ]
    )
    jobs._run(graph, "job-1", "a timer", 50)

    view = jobs.public_view(jobs.get_job("job-1"))
    assert view["builder_mode"] == "loop"
    assert view["activity"] == ["Writing src/App.jsx", "Build passed"]
    assert view["status"] == "succeeded"


def test_only_the_latest_steps_are_kept():
    jobs.create_job("job-2", "a timer", "loop")
    for i in range(jobs.MAX_ACTIVITY + 5):
        jobs._add_activity("job-2", f"step {i}")
    activity = jobs.get_job("job-2")["activity"]
    assert len(activity) == jobs.MAX_ACTIVITY
    assert activity[-1] == f"step {jobs.MAX_ACTIVITY + 4}"


def test_pipeline_jobs_have_no_activity():
    jobs.create_job("job-3", "a timer")
    view = jobs.public_view(jobs.get_job("job-3"))
    assert view["builder_mode"] == "pipeline"
    assert view["activity"] == []
