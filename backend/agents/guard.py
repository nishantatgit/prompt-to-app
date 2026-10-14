from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, model_validator

GUARD_PROMPT = (Path(__file__).parent / "prompts" / "guard.md").read_text()

PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content=GUARD_PROMPT),
    ("human", "<user_request>{prompt}</user_request>"),
])


class GuardResult(BaseModel):
    category: Literal[
        "allowed", "malicious", "prompt_injection",
        "irrelevant", "unsupported", "unclear",
    ]
    reason: str

    @model_validator(mode="after")
    def reason_required_when_rejected(self):
        if self.category != "allowed" and not self.reason.strip():
            raise ValueError("reason is required when the request is not allowed")
        return self


def make_guard(llm: BaseChatModel):
    chain = PROMPT | llm.with_structured_output(GuardResult, include_raw=True)

    def guard(state: dict) -> dict:
        out = chain.invoke({"prompt": state["prompt"]})

        if out["parsing_error"] is not None:
            # Fail closed: never let an unvalidated request through
            return {
                "allowed": False,
                "guard_category": "error",
                "guard_reason": "Could not validate the request. Please try again.",
            }

        result: GuardResult = out["parsed"]
        return {
            "allowed": result.category == "allowed",
            "guard_category": result.category,
            "guard_reason": result.reason,
        }

    return guard