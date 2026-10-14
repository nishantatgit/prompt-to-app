from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI


def create_llm(provider: str, model: str, api_key: str, temperature: float = 0) -> BaseChatModel:
    if provider == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature)
    if provider == "openai":
        return ChatOpenAI(model=model, api_key=api_key, temperature=temperature)
    raise ValueError(f"Unsupported provider: {provider}")