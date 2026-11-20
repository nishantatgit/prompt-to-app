import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI


def create_llm(provider: str, model: str, api_key: str, callbacks=None) -> BaseChatModel:
    """callbacks: such as a UsageMeter, called after every reply."""
    if provider == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key, callbacks=callbacks)
    if provider == "openai":
        return ChatOpenAI(model=model, api_key=api_key, callbacks=callbacks)
    raise ValueError(f"Unsupported provider: {provider}")


# Anthropic turns a json_schema into a grammar before answering, and refuses
# schemas whose grammar is too large with a 400 such as "The compiled grammar
# is too large, which would cause performance issues." Nothing is generated,
# so the same request can be asked again without the grammar.
GRAMMAR_TOO_LARGE = re.compile(r"grammar is too large|too many strict tools", re.IGNORECASE)

# (model class, model name, schema) that Anthropic refused, so later calls
# skip straight to the fallback instead of being refused again.
_NO_GRAMMAR: set[tuple[str, str, str]] = set()


def grammar_too_large(error: Exception) -> bool:
    return bool(GRAMMAR_TOO_LARGE.search(str(error)))


def _json_text(text: str) -> str:
    """The JSON object in a reply, without a ```json fence or words around it."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def _reply_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block) for block in content
    )


def _answer_as_json(llm: BaseChatModel, schema, input, config=None) -> dict:
    """The same request without native structured output: the schema goes in
    the prompt and Pydantic checks the reply. A reply that doesn't fit comes
    back as parsing_error, like a structured answer that failed validation, so
    each agent's own retry with feedback handles it."""
    messages = input.to_messages() if hasattr(input, "to_messages") else list(input)
    instructions = (
        "Reply with only one JSON object, no other text, that matches this JSON schema:\n"
        + json.dumps(schema.model_json_schema())
    )
    raw = llm.invoke([*messages, HumanMessage(content=instructions)], config)
    try:
        parsed = schema.model_validate(json.loads(_json_text(_reply_text(raw))))
        error = None
    except Exception as e:
        parsed, error = None, e
    return {"raw": raw, "parsed": parsed, "parsing_error": error}


def structured(llm: BaseChatModel, schema):
    """The model, answering with `schema`, plus the raw reply for error messages.

    json_schema uses each provider's native structured output. Anthropic does
    not support forced tool calling on its newer models, which was the
    default here, and OpenAI already defaults to json_schema.

    When Anthropic refuses the schema as too large a grammar, the request is
    asked again with the schema in the prompt instead (see _answer_as_json).
    """
    native = llm.with_structured_output(schema, include_raw=True, method="json_schema")
    name = schema.__name__
    key = (type(llm).__name__, str(getattr(llm, "model", "")), name)

    def run(input, config=None):
        if key not in _NO_GRAMMAR:
            try:
                return native.invoke(input, config)
            except Exception as error:
                if not grammar_too_large(error):
                    raise
                _NO_GRAMMAR.add(key)
                record = {"schema": name, "model": key[1]}
                print(f"structured_output_fallback {json.dumps(record)}", flush=True)
        return _answer_as_json(llm, schema, input, config)

    return RunnableLambda(run)
