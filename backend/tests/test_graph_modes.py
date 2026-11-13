import pytest

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.stub_llm import StubLLM

AGENTS = ["guard", "analyst", "architect", "test_planner", "builder", "validator"]


@pytest.fixture
def parts(tmp_path):
    models = AgentModels(**{a: StubLLM(agent=a) for a in AGENTS})
    limits = AgentLimits(2, 2, 2, 3, 2)
    return models, limits, tmp_path


def shape(graph):
    g = graph.get_graph()
    nodes = set(g.nodes) - {"__start__", "__end__"}
    edges = {(e.source, e.target) for e in g.edges}
    return nodes, edges


def test_pipeline_is_the_default_and_unchanged(parts):
    nodes, edges = shape(build_graph(*parts))
    assert {"builder", "build_check", "build_done"} <= nodes
    assert ("builder", "build_check") in edges
    assert ("build_check", "builder") in edges  # retry routed through the graph
    assert ("build_check", "migrations") in edges
    assert ("migrations", "build_done") in edges


def test_loop_mode_replaces_the_builder_and_build_check(parts):
    nodes, edges = shape(build_graph(*parts, builder_mode="loop"))
    assert "build_check" not in nodes
    assert {"builder", "build_done"} <= nodes
    assert ("builder", "migrations") in edges
    assert ("builder", "__end__") in edges  # a failed loop ends the job
    assert ("builder", "builder") not in edges  # retries happen inside the loop


def test_both_modes_share_everything_else(parts):
    pipeline_nodes, pipeline_edges = shape(build_graph(*parts))
    loop_nodes, loop_edges = shape(build_graph(*parts, builder_mode="loop"))
    assert pipeline_nodes - {"build_check"} == loop_nodes

    def outside_build(edges):
        build = {"builder", "build_check"}
        return {e for e in edges if not build & set(e)}

    assert outside_build(pipeline_edges) == outside_build(loop_edges)


def test_the_database_comes_before_the_build_and_migrations_after(parts):
    for mode in ("pipeline", "loop"):
        nodes, edges = shape(build_graph(*parts, builder_mode=mode))
        assert {"database", "migrations"} <= nodes
        assert ("setup_workspace", "database") in edges
        assert ("database", "builder") in edges
        assert ("database", "__end__") in edges
        assert ("setup_workspace", "builder") not in edges
        assert ("migrations", "build_done") in edges
        assert ("migrations", "__end__") in edges
        assert ("build_done", "test_executor") in edges


def test_a_failed_database_step_ends_the_job_cleanly(parts, monkeypatch):
    """The database step runs alongside the test planner; when it fails the
    graph must end with the reason, not crash on a conflicting update."""
    import os

    from agents import graph as graph_module
    from agents.database import make_database

    def failing(token, name, config_id):
        raise RuntimeError("Vercel 402: payment required")

    monkeypatch.setattr(
        graph_module, "make_database", lambda t, c: make_database(t, c, provision=failing)
    )
    monkeypatch.setenv("STUB_SCENARIO", "guestbook")
    from agents.stub_llm import StubLLM

    models, limits, tmp = parts
    models = AgentModels(**{a: StubLLM(agent=a, scenario="guestbook") for a in AGENTS})
    g = build_graph(models, limits, tmp, vercel_token="tok", supabase_config_id="icfg", builder_mode="loop")
    state = g.invoke(
        {"prompt": "A guestbook where visitors leave a name and message", "job_id": "26-11-13-1-abcdef1234"},
        {"recursion_limit": 50},
    )
    assert state["database_error"].startswith("Could not create the app's database: Vercel 402")
    assert not state.get("build_ok")
    assert os.path.isdir(tmp)
