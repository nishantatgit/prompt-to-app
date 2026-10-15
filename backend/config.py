from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent / ".env"

Provider = Literal["anthropic", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    guard_provider: Provider
    guard_model: str
    architect_provider: Provider
    architect_model: str
    test_planner_provider: Provider
    test_planner_model: str
    builder_provider: Provider
    builder_model: str
    validator_provider: Provider
    validator_model: str

    analyst_max_attempts: int
    architect_max_attempts: int
    test_planner_max_attempts: int
    builder_max_attempts: int
    validator_max_attempts: int
    graph_recursion_limit: int

    workspaces_dir: Path

    def api_key_for(self, provider: Provider) -> str:
        key = self.anthropic_api_key if provider == "anthropic" else self.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise ValueError(f"No API key set for provider '{provider}'")
        return key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
