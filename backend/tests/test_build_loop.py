from itertools import count

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.build_loop import make_build_loop

ARCHITECTURE = {"summary": "A counter app"}


class ScriptedModel:
    """Stands in for a chat model: returns the scripted answers in order and
    records every message list it was called with."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def bind_tools(self, tools):
        self.tool_names = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.calls.append(list(messages))
        return self.answers.pop(0)


_ids = count(1)


def tool(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"call-{next(_ids)}"}]
    )


def done(text="Done."):
    return AIMessage(content=text)


class ScriptedBuild:
    def __init__(self, *results):
        self.results = list(results)
        self.runs = 0

    def __call__(self, state):
        self.runs += 1
        ok, log = self.results.pop(0)
        return {"build_ok": ok, "build_log": log}


@pytest.fixture
def state(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.jsx").write_text("export default function App() {}\n")
    return {"workspace_dir": str(tmp_path), "architecture": ARCHITECTURE}


def run(state, model, build, **limits):
    return make_build_loop(model, build=build, **limits)(state)


def test_writes_files_then_passes_the_build(state, tmp_path):
    model = ScriptedModel(
        [tool("write_file", path="src/App.jsx", content="export default () => 1\n"), done()]
    )
    build = ScriptedBuild((True, "built"))

    out = run(state, model, build)

    assert out["build_ok"] is True
    assert out["files_written"] == ["src/App.jsx"]
    assert out["builder_attempts"] == 1
    assert (tmp_path / "src" / "App.jsx").read_text() == "export default () => 1\n"
    assert model.tool_names == ["write_file", "read_file", "edit_file", "list_files"]


def test_sends_the_architecture_and_the_prompt(state):
    model = ScriptedModel([done()])
    run(state, model, ScriptedBuild((True, "")))

    system, user = model.calls[0]
    assert "edit_file" in system.content
    assert "A counter app" in user.content


def test_tool_results_go_back_to_the_model(state):
    model = ScriptedModel([tool("read_file", path="src/App.jsx"), done()])
    run(state, model, ScriptedBuild((True, "")))

    answer = model.calls[1][-1]
    assert isinstance(answer, ToolMessage)
    assert "export default function App" in answer.content


def test_a_failed_build_sends_the_log_and_continues(state, tmp_path):
    model = ScriptedModel(
        [
            done("First try."),
            tool("edit_file", path="src/App.jsx", old="App()", new="App(props)"),
            done("Fixed."),
        ]
    )
    build = ScriptedBuild((False, "ERROR: Unexpected token at App.jsx:1"), (True, "built"))

    out = run(state, model, build)

    assert out["build_ok"] is True
    assert out["builder_attempts"] == 2
    feedback = model.calls[1][-1]
    assert isinstance(feedback, HumanMessage)
    assert "Unexpected token" in feedback.content
    assert "App(props)" in (tmp_path / "src" / "App.jsx").read_text()


def test_stops_after_max_builds(state):
    model = ScriptedModel([done(), done(), done()])
    build = ScriptedBuild((False, "fail 1"), (False, "fail 2"), (False, "fail 3"))

    out = run(state, model, build, max_builds=3)

    assert out["build_ok"] is False
    assert out["builder_attempts"] == 3
    assert out["build_log"] == "fail 3"


def test_stops_at_the_turn_cap(state):
    model = ScriptedModel([tool("list_files") for _ in range(5)])
    build = ScriptedBuild()

    out = run(state, model, build, max_turns=5)

    assert out["build_ok"] is False
    assert build.runs == 0
    assert "Stopped after 5 model turns" in out["build_log"]


def test_tool_errors_and_unknown_tools_come_back_as_text(state):
    model = ScriptedModel(
        [
            tool("edit_file", path="src/App.jsx", old="nope", new="x"),
            tool("delete_everything"),
            done(),
        ]
    )
    run(state, model, ScriptedBuild((True, "")))

    assert "not found" in model.calls[1][-1].content
    assert "no tool named delete_everything" in model.calls[2][-1].content


def test_only_the_end_of_a_long_build_log_is_sent(state):
    long_log = "x" * 10_000 + "THE REAL ERROR"
    model = ScriptedModel([done(), done()])
    run(state, model, ScriptedBuild((False, long_log), (True, "")))

    feedback = model.calls[1][-1].content
    assert "THE REAL ERROR" in feedback
    assert len(feedback) < 5_000
