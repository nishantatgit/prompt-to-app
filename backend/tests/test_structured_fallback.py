import json

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from agents import llm as llm_module
from agents.llm import grammar_too_large, structured

# The error Nishant saw on a prod build, as the Anthropic SDK words it.
REFUSED = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'The compiled grammar is too large, which would cause performance "
    "issues. Simplify your tool schemas or reduce the number of strict tools.'}, "
    "'request_id': 'req_011ChDUsejGtVzxnPKJkt8mt'}"
)

PROMPT = ChatPromptTemplate.from_messages([("system", "You plan apps."), ("human", "{prompt}")])


class Plan(BaseModel):
    name: str
    steps: list[str] = Field(min_length=1)


class FakeModel(BaseChatModel):
    """Refuses native structured output with `native_error`, and answers
    plain calls with `replies` in turn, recording what it was sent."""

    native_error: str | None = REFUSED
    replies: list[str] = []
    model: str = "claude-fake"
    sent: list = []
    native_calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake"

    def with_structured_output(self, schema, **kwargs):
        def native(_input):
            self.native_calls += 1
            if self.native_error:
                raise RuntimeError(self.native_error)
            return {
                "raw": AIMessage(content="{}"),
                "parsed": schema(name="native", steps=["a"]),
                "parsing_error": None,
            }

        return RunnableLambda(native)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.sent.append(messages)
        text = self.replies[len(self.sent) - 1]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


@pytest.fixture(autouse=True)
def fresh_memory(monkeypatch):
    monkeypatch.setattr(llm_module, "_NO_GRAMMAR", set())


def test_the_prod_error_is_recognised():
    assert grammar_too_large(RuntimeError(REFUSED))
    assert not grammar_too_large(RuntimeError("Error code: 400 - prompt is too long"))


def test_a_refused_schema_is_asked_again_with_the_schema_in_the_prompt():
    model = FakeModel(
        replies=['```json\n{"name": "Tip calculator", "steps": ["bill", "split"]}\n```']
    )
    out = (PROMPT | structured(model, Plan)).invoke({"prompt": "A tip calculator"})

    assert out["parsing_error"] is None
    assert out["parsed"] == Plan(name="Tip calculator", steps=["bill", "split"])
    sent = model.sent[0]
    # The original conversation, then the schema as the last message.
    assert [m.type for m in sent] == ["system", "human", "human"]
    assert sent[1].content == "A tip calculator"
    assert json.dumps(Plan.model_json_schema()) in sent[2].content


def test_a_reply_that_does_not_fit_is_a_parsing_error_for_the_agent_to_retry():
    model = FakeModel(replies=['Here you go: {"name": "Tip calculator", "steps": []}'])
    out = (PROMPT | structured(model, Plan)).invoke({"prompt": "A tip calculator"})
    assert out["parsed"] is None
    assert "steps" in str(out["parsing_error"])
    assert out["raw"].content.startswith("Here you go")


def test_once_refused_the_schema_skips_the_native_call():
    model = FakeModel(replies=['{"name": "a", "steps": ["x"]}', '{"name": "b", "steps": ["y"]}'])
    chain = PROMPT | structured(model, Plan)
    chain.invoke({"prompt": "one"})
    chain.invoke({"prompt": "two"})
    assert model.native_calls == 1
    assert len(model.sent) == 2


def test_other_errors_still_fail_the_call():
    model = FakeModel(native_error="Error code: 529 - overloaded")
    with pytest.raises(RuntimeError, match="overloaded"):
        (PROMPT | structured(model, Plan)).invoke({"prompt": "A tip calculator"})
    assert model.sent == []


def test_native_structured_output_is_used_when_it_works():
    model = FakeModel(native_error=None)
    out = (PROMPT | structured(model, Plan)).invoke({"prompt": "A tip calculator"})
    assert out["parsed"].name == "native"
    assert model.sent == []
