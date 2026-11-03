"""Canned LLM answers, so the whole build flow can run without calling a model.

Turn it on with STUB_LLM=true. Every agent then gets a StubLLM that returns a
fixed answer from agents/stubs/<scenario>/, while every other step runs for
real: the analyst and architect checks, the workspace, yarn build, the test
writer, Playwright and deploy.

The fixtures are for the tip calculator, so submit its benchmark prompt:
"A tip calculator: bill amount, tip percent, number of people". The analyst
still checks that its quotes appear in the prompt, so another prompt fails
there, as a real run would.
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

    def _fixture(self, extension: str) -> Path:
        path = STUBS_DIR / self.scenario / f"{self.agent}{extension}"
        if not path.exists():
            raise FileNotFoundError(f"No stub answer for {self.agent}: {path}")
        return path

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


def make_stub_models(agents) -> dict:
    """One StubLLM per agent name, ready for AgentModels(**...)."""
    scenario = os.environ.get("STUB_SCENARIO", DEFAULT_SCENARIO)
    return {agent: StubLLM(agent=agent, scenario=scenario) for agent in agents}
