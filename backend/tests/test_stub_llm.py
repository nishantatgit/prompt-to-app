from agents.build_loop import make_build_loop
from agents.stub_llm import StubLLM


class Build:
    def __init__(self, *results):
        self.results = list(results)

    def __call__(self, state):
        ok = self.results.pop(0)
        return {"build_ok": ok, "build_log": "" if ok else "Expected ')' in src/App.jsx"}


def state(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.jsx").write_text("export default function App() {}\n")
    return {"workspace_dir": str(tmp_path), "architecture": {"summary": "tip calculator"}}


def test_script_plays_tool_calls_then_done():
    turns = StubLLM(agent="builder").bind_tools([])
    first, second, third = (turns.invoke([]) for _ in range(3))
    assert first.tool_calls[0]["name"] == "list_files"
    assert second.tool_calls[0]["name"] == "write_file"
    assert "calculatePerPerson" in second.tool_calls[0]["args"]["content"]
    assert not third.tool_calls


def test_each_binding_starts_the_script_again():
    llm = StubLLM(agent="builder")
    llm.bind_tools([]).invoke([])
    assert llm.bind_tools([]).invoke([]).tool_calls[0]["name"] == "list_files"


def test_scenario_falls_back_to_the_default_fixtures():
    guard = StubLLM(agent="guard", scenario="tip-calculator-retry")
    assert guard._fixture(".json").parent.name == "tip-calculator"


def test_loop_with_the_default_script(tmp_path):
    out = make_build_loop(StubLLM(agent="builder"), build=Build(True))(state(tmp_path))
    assert out["build_ok"] is True
    assert out["files_written"] == ["src/App.jsx"]
    assert "calculatePerPerson" in (tmp_path / "src" / "App.jsx").read_text()


def test_loop_with_the_retry_script(tmp_path):
    llm = StubLLM(agent="builder", scenario="tip-calculator-retry")
    out = make_build_loop(llm, build=Build(False, True))(state(tmp_path))
    assert out["build_ok"] is True
    assert out["builder_attempts"] == 2
    assert "(1 + tipPercent / 100)) / people" in (tmp_path / "src" / "App.jsx").read_text()


def test_an_unknown_scenario_is_an_error(monkeypatch):
    import pytest

    from agents.stub_llm import make_stub_models

    monkeypatch.setenv("STUB_SCENARIO", "no-such-app")
    with pytest.raises(ValueError, match="Unknown STUB_SCENARIO 'no-such-app'"):
        make_stub_models(["guard"])


def test_the_guestbook_scenario_passes_every_planning_agent():
    from agents.analyst import make_analyst
    from agents.architect import make_architect
    from agents.stub_llm import StubLLM
    from agents.test_planner import make_test_planner

    state = {"prompt": "A guestbook where visitors leave a name and message", "job_id": "x"}
    for agent, make, key in [
        ("analyst", make_analyst, "requirements"),
        ("architect", make_architect, "architecture"),
        ("test_planner", make_test_planner, "test_plan"),
    ]:
        out = make(StubLLM(agent=agent, scenario="guestbook"))(state)
        assert out.get(key), out
        state.update(out)
    assert state["architecture"]["storage"] == "supabase"
