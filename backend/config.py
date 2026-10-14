from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent / ".env"

Provider = Literal["anthropic", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    guard_provider: Provider
    guard_model: str
    planner_provider: Provider
    planner_model: str
    builder_provider: Provider
    builder_model: str
    validator_provider: Provider
    validator_model: str

    workspaces_dir: Path

    planner_max_attempts: int
    builder_max_attempts: int
    validator_max_attempts: int
    graph_recursion_limit: int

    @model_validator(mode="after")
    def keys_present_for_used_providers(self):
        used = {
            self.guard_provider, self.planner_provider,
            self.builder_provider, self.validator_provider,
        }
        keys = {"anthropic": self.anthropic_api_key, "openai": self.openai_api_key}
        missing = [p for p in used if not keys[p] or not keys[p].get_secret_value()]
        if missing:
            raise ValueError(f"Missing API key for provider(s): {', '.join(missing)}")
        return self

    def api_key_for(self, provider: Provider) -> str:
        key = self.anthropic_api_key if provider == "anthropic" else self.openai_api_key
        return key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()