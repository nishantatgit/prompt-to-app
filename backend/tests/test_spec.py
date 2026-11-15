import json
from pathlib import Path

from tools.spec import make_save_spec, read_spec, write_spec
from tools.vercel import collect_files

STUBS = Path(__file__).parent.parent / "agents" / "stubs" / "guestbook"


def guestbook_state(tmp_path, prompt="A guestbook where visitors leave a name and message"):
    return {
        "job_id": "26-11-15-1-abcdef1234",
        "prompt": prompt,
        "workspace_dir": str(tmp_path),
        "requirements": json.loads((STUBS / "analyst.json").read_text()),
        "architecture": json.loads((STUBS / "architect.json").read_text()),
        "test_plan": json.loads((STUBS / "test_planner.json").read_text()),
        "confidence": 100.0,
    }


def test_the_spec_reads_back_exactly_as_written(tmp_path):
    state = guestbook_state(tmp_path)
    write_spec(tmp_path, state, now=0)

    spec = read_spec(tmp_path)
    assert spec["requirements"] == state["requirements"]
    assert spec["architecture"] == state["architecture"]
    assert spec["test_plan"] == state["test_plan"]
    assert spec["history"] == [
        {
            "job_id": "26-11-15-1-abcdef1234",
            "prompt": "A guestbook where visitors leave a name and message",
            "at": "1970-01-01T00:00:00Z",
            "confidence": 100.0,
        }
    ]


def test_each_build_adds_its_prompt_to_the_history(tmp_path):
    write_spec(tmp_path, guestbook_state(tmp_path), now=0)
    later = guestbook_state(tmp_path, prompt="Let visitors delete their own entry")
    later["job_id"] = "26-11-15-2-bbbbbb2222"
    write_spec(tmp_path, later, now=60)

    history = read_spec(tmp_path)["history"]
    assert [h["prompt"] for h in history] == [
        "A guestbook where visitors leave a name and message",
        "Let visitors delete their own entry",
    ]


def test_the_readme_explains_the_app_to_a_person(tmp_path):
    write_spec(tmp_path, guestbook_state(tmp_path), now=0)
    text = (tmp_path / "spec" / "README.md").read_text()

    assert text.startswith("# Guestbook where visitors leave a name and a message")
    assert "1. A guestbook where visitors leave a name and message (1970-01-01)" in text
    assert "- **R1** (explicit): A visitor leaves their name and a message" in text
    assert "### F1: Sign the guestbook" in text
    assert "- **guestbook_entries** (id, created_at, name, message)" in text
    assert "  - Anyone can add an entry" in text
    assert "- E2 (F1-AC2): A signed entry is saved and survives a reload" in text
    assert "Last run: 100.0% of tests passed." in text


def test_a_folder_without_a_spec_reads_as_none(tmp_path):
    assert read_spec(tmp_path) is None


def test_the_spec_is_never_deployed(tmp_path):
    (tmp_path / "index.html").write_text("<div></div>")
    write_spec(tmp_path, guestbook_state(tmp_path), now=0)
    assert [f["file"] for f in collect_files(tmp_path)] == ["index.html"]


def test_the_graph_step_writes_into_the_workspace(tmp_path):
    assert make_save_spec()(guestbook_state(tmp_path)) == {}
    assert (tmp_path / "spec" / "architecture.json").exists()


def test_the_spec_is_saved_after_the_tests_and_before_deploy():
    from agents.graph import AgentLimits, AgentModels, build_graph
    from agents.stub_llm import StubLLM

    agents = ["guard", "analyst", "architect", "test_planner", "builder", "validator"]
    models = AgentModels(**{a: StubLLM(agent=a) for a in agents})
    graph = build_graph(models, AgentLimits(2, 2, 2, 3, 2), Path("/tmp"), builder_mode="loop")
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("test_executor", "save_spec") in edges
    assert ("save_spec", "deploy") in edges
    assert ("test_executor", "deploy") not in edges
