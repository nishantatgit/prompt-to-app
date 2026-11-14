"""Canned LLM answers, so the whole build flow can run without calling a model.

Turn it on with STUB_LLM=true. Every agent then gets a StubLLM that returns a
fixed answer from agents/stubs/<scenario>/, while every other step runs for
real: the analyst and architect checks, the workspace, yarn build, the test
writer, Playwright and deploy.

The fixtures are for the tip calculator, so submit its benchmark prompt:
"A tip calculator: bill amount, tip percent, number of people". The analyst
still checks that its quotes appear in the prompt, so another prompt fails
there, as a real run would.

In BUILDER_MODE=loop the builder works with tools, so its stub follows a
script, builder_loop.json: a list of steps, each either a tool call
({"tool": ..., "args": {...}}) or the end of a turn ({"done": "..."}). A
"content_file" argument is replaced by that fixture file's text. A scenario
folder only needs the files that differ; the rest come from tip-calculator.
For example STUB_SCENARIO=tip-calculator-retry breaks the build on purpose and
then fixes it, to exercise the loop's retry path.
"""

import json
import os
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

STUBS_DIR = Path(__file__).parent / "stubs"
DEFAULT_SCENARIO = "tip-calculator"


def stub_mode() -> bool:
    return os.environ.get("STUB_LLM", "").lower() == "true"


class StubLLM(BaseChatModel):
    """Answers for one agent, read from <agent>.json or <agent>.jsx."""

    agent: str
    scenario: str = DEFAULT_SCENARIO

    @property
    def _llm_type(self) -> str:
        return "stub"

    def _fixture(self, extension: str, name: str | None = None) -> Path:
        filename = name or f"{self.agent}{extension}"
        for scenario in (self.scenario, DEFAULT_SCENARIO):
            path = STUBS_DIR / scenario / filename
            if path.exists():
                return path
        raise FileNotFoundError(f"No stub file {filename} in {self.scenario}")

    # The build loop calls llm.bind_tools(tools), then invoke() once per turn.
    # Each binding plays the script from the start.
    def bind_tools(self, tools, **kwargs):
        steps = json.loads(self._fixture("", name="builder_loop.json").read_text())
        return _ScriptedTurns(steps, self._fixture)

    # The builder calls llm.invoke() and reads the text of the answer.
    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        text = self._fixture(".jsx").read_text()
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    # The other agents call llm.with_structured_output(Schema, include_raw=True).
    # The answer goes through the real schema, so a fixture that breaks a
    # validator fails the same way a model's answer would.
    def with_structured_output(self, schema, *, include_raw: bool = False, **kwargs):
        raw_text = self._fixture(".json").read_text()

        def answer(_input):
            raw = AIMessage(content=raw_text)
            try:
                parsed = schema.model_validate(json.loads(raw_text))
                error = None
            except Exception as e:
                parsed, error = None, e
            if include_raw:
                return {"raw": raw, "parsed": parsed, "parsing_error": error}
            if error:
                raise error
            return parsed

        return RunnableLambda(answer)


class _ScriptedTurns:
    def __init__(self, steps: list[dict], fixture):
        self.steps = list(steps)
        self.fixture = fixture
        self.turn = 0

    def invoke(self, messages) -> AIMessage:
        if not self.steps:
            return AIMessage(content="Stub script finished.")
        self.turn += 1
        step = self.steps.pop(0)
        if "done" in step:
            return AIMessage(content=step["done"])
        args = dict(step.get("args", {}))
        if "content_file" in args:
            args["content"] = self.fixture("", name=args.pop("content_file")).read_text()
        call = {"name": step["tool"], "args": args, "id": f"stub-{self.turn}"}
        return AIMessage(content="", tool_calls=[call])


def make_stub_models(agents) -> dict:
    """One StubLLM per agent name, ready for AgentModels(**...)."""
    scenario = os.environ.get("STUB_SCENARIO", DEFAULT_SCENARIO)
    # A missing scenario would quietly fall back to the default answers and
    # test the wrong app, so it is an error.
    if not (STUBS_DIR / scenario).is_dir():
        raise ValueError(f"Unknown STUB_SCENARIO '{scenario}': no folder in {STUBS_DIR}")
    return {agent: StubLLM(agent=agent, scenario=scenario) for agent in agents}
