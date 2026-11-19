"""One or two questions before building, only when the answer changes the app.

Runs before a build, outside the build graph, on the cheap guard model. It
never blocks building: any failure means no questions.
"""

from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.llm import structured

CLARIFIER_PROMPT = (Path(__file__).parent / "prompts" / "clarifier.md").read_text()

PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=CLARIFIER_PROMPT),
        ("human", "<user_request>{prompt}</user_request>"),
    ]
)

MAX_QUESTIONS = 2
NOT_SURE = "I'm not sure"


class Question(BaseModel):
    question: str = Field(description="Short, plain, friendly question.")
    options: list[str] = Field(description="2 to 4 short answers, a few words each.")


class Questions(BaseModel):
    questions: list[Question] = Field(description="0 to 2 questions; usually none.")


def _clean(questions: list[Question]) -> list[dict]:
    out = []
    for q in questions[:MAX_QUESTIONS]:
        text = q.question.strip()
        options = [o.strip() for o in q.options if o.strip() and o.strip() != NOT_SURE][:4]
        if text and len(options) >= 2:
            out.append({"question": text[:200], "options": [o[:60] for o in options]})
    return out


def ask(llm: BaseChatModel, prompt: str) -> list[dict]:
    """The questions worth asking about this request, often none."""
    try:
        out = (PROMPT | structured(llm, Questions)).invoke({"prompt": prompt})
    except Exception:
        return []
    if out.get("parsing_error") is not None or out.get("parsed") is None:
        return []
    return _clean(out["parsed"].questions)


def with_answers(prompt: str, answers: list[dict]) -> str:
    """The request plus the answers, so the builder sees both. "I'm not sure"
    leaves the choice to the builder."""
    lines = []
    for a in answers:
        question = (a.get("question") or "").strip()
        answer = (a.get("answer") or "").strip()
        if not question or not answer:
            continue
        if answer == NOT_SURE:
            answer = "Not sure, choose what fits best."
        lines.append(f"- {question} {answer}")
    if not lines:
        return prompt
    return f"{prompt.rstrip()}\n\nMore details:\n" + "\n".join(lines)
