import re
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, model_validator

ANALYST_PROMPT = (Path(__file__).parent / "prompts" / "analyst.md").read_text()

PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=ANALYST_PROMPT),
        ("human", "<user_request>{prompt}</user_request>\n\n{feedback}"),
    ]
)

MIN_QUOTE_LENGTH = 3


class Requirement(BaseModel):
    id: str = Field(pattern=r"^R\d+$")
    kind: Literal["explicit", "implied"]
    statement: str = Field(min_length=1)
    source_quote: str = Field(
        default="", description="Exact words from the request. Required for explicit requirements."
    )
    reason: str = Field(
        default="", description="Why it is needed. Required for implied requirements."
    )

    @model_validator(mode="after")
    def evidence(self):
        if self.kind == "explicit" and not self.source_quote.strip():
            raise ValueError(f"explicit requirement {self.id} needs a source_quote")
        if self.kind == "implied" and not self.reason.strip():
            raise ValueError(f"implied requirement {self.id} needs a reason")
        return self


class Requirements(BaseModel):
    app_summary: str
    requirements: list[Requirement] = Field(min_length=1)
    out_of_scope: list[str]
    assumptions: list[str]

    @model_validator(mode="after")
    def check(self):
        ids = [r.id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement ids must be unique")
        if not any(r.kind == "explicit" for r in self.requirements):
            raise ValueError("at least one requirement must be explicit")
        return self

    def ids(self) -> set[str]:
        return {r.id for r in self.requirements}


def _normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[^\w\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def check_against_prompt(reqs: Requirements, prompt: str) -> list[str]:
    """Every explicit requirement must quote words that really appear in the prompt."""
    errors = []
    normalized_prompt = _normalize(prompt)
    for r in reqs.requirements:
        if r.kind != "explicit":
            continue
        quote = _normalize(r.source_quote)
        if len(quote) < MIN_QUOTE_LENGTH:
            errors.append(f"requirement {r.id}: source_quote '{r.source_quote}' is too short")
        elif quote not in normalized_prompt:
            errors.append(
                f"requirement {r.id}: source_quote '{r.source_quote}' does not appear in the "
                "request. Quote the request exactly, or mark the requirement as implied with a reason."
            )
    return errors


def make_analyst(llm: BaseChatModel):
    chain = PROMPT | llm.with_structured_output(Requirements, include_raw=True)

    def analyst(state: dict) -> dict:
        attempts = state.get("analyst_attempts", 0) + 1
        previous_error = state.get("analyst_feedback", "")

        feedback = ""
        if previous_error:
            feedback = (
                "Your previous requirements were rejected with these errors:\n"
                f"{previous_error}\n"
                "Return corrected requirements that fix all of them."
            )

        out = chain.invoke({"prompt": state["prompt"], "feedback": feedback})

        if out["parsing_error"] is not None:
            problems = [str(out["parsing_error"])]
        else:
            problems = check_against_prompt(out["parsed"], state["prompt"])

        if problems:
            return {
                "requirements": None,
                "analyst_attempts": attempts,
                "analyst_feedback": "\n".join(f"- {p}" for p in problems),
                "errors": [f"Requirements failed: {p}" for p in problems],
            }

        return {
            "requirements": out["parsed"].model_dump(),
            "analyst_attempts": attempts,
            "analyst_feedback": "",
            "errors": [],
        }

    return analyst
