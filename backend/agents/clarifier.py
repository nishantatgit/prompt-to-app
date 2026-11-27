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


# Answers that mean the same as the "I'm not sure" button the app adds itself.
# Compared after _key(), so case, curly apostrophes and a trailing dot or
# question mark do not matter.
_NOT_SURE_LIKE = {"i'm not sure", "im not sure", "not sure", "unsure", "i don't know", "don't know"}


def _key(text: str) -> str:
    """The text as a person reads it: same words, any case or apostrophe."""
    text = text.replace("’", "'").replace("‘", "'")
    return " ".join(text.casefold().split()).rstrip(".?!")


def _clean(questions: list[Question]) -> list[dict]:
    out = []
    seen_questions = set()
    for q in questions:
        if len(out) == MAX_QUESTIONS:
            break
        text = q.question.strip()[:200]
        if not text or _key(text) in seen_questions:
            continue
        # Each answer once, and never a second "not sure": the app shows its
        # own, and two buttons with the same words would both light up.
        options, seen = [], set()
        for option in q.options:
            option = option.strip()[:60].strip()
            key = _key(option)
            if not key or key in seen or key in _NOT_SURE_LIKE:
                continue
            seen.add(key)
            options.append(option)
        options = options[:4]
        if len(options) >= 2:
            seen_questions.add(_key(text))
            out.append({"question": text, "options": options})
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
