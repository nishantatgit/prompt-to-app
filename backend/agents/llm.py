from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI


def create_llm(provider: str, model: str, api_key: str, callbacks=None) -> BaseChatModel:
    """callbacks: such as a UsageMeter, called after every reply."""
    if provider == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key, callbacks=callbacks)
    if provider == "openai":
        return ChatOpenAI(model=model, api_key=api_key, callbacks=callbacks)
    raise ValueError(f"Unsupported provider: {provider}")


def structured(llm: BaseChatModel, schema):
    """The model, answering with `schema`, plus the raw reply for error messages.

    json_schema uses each provider's native structured output. Anthropic does
    not support forced tool calling on its newer models, which was the
    default here, and OpenAI already defaults to json_schema.
    """
    return llm.with_structured_output(schema, include_raw=True, method="json_schema")
