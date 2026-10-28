import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.llm import create_llm
from api.jobs import create_job, get_job, public_view, submit
from config import Settings, get_settings
from tools.workspace import new_job_id

router = APIRouter(prefix="/api")

# Used when the user's provider differs from the one configured for an agent.
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-6.1-sol"}

# Settings have no separate analyst entry; the analyst uses the guard settings.
SETTINGS_PREFIX = {
    "guard": "guard",
    "analyst": "guard",
    "architect": "architect",
    "test_planner": "test_planner",
    "builder": "builder",
    "validator": "validator",
}


class BuildRequest(BaseModel):
    prompt: str
    provider: Literal["anthropic", "openai"]
    api_key: SecretStr | None = None


def make_models(provider: str, api_key: str, settings: Settings) -> AgentModels:
    def llm(agent: str):
        prefix = SETTINGS_PREFIX[agent]
        if getattr(settings, f"{prefix}_provider") == provider:
            model = getattr(settings, f"{prefix}_model")
        else:
            model = DEFAULT_MODEL[provider]
        return create_llm(provider, model, api_key)

    return AgentModels(**{agent: llm(agent) for agent in SETTINGS_PREFIX})


def get_agent_limits(settings: Settings = Depends(get_settings)) -> AgentLimits:
    return AgentLimits(
        analyst_max_attempts=settings.analyst_max_attempts,
        architect_max_attempts=settings.architect_max_attempts,
        test_planner_max_attempts=settings.test_planner_max_attempts,
        builder_max_attempts=settings.builder_max_attempts,
        validator_max_attempts=settings.validator_max_attempts,
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/build", status_code=202)
def build(
    req: BuildRequest,
    limits: AgentLimits = Depends(get_agent_limits),
    settings: Settings = Depends(get_settings),
):
    if req.api_key:
        key = req.api_key.get_secret_value()
    elif os.environ.get("ALLOW_SERVER_KEYS") == "true":
        key = settings.api_key_for(req.provider)
    else:
        raise HTTPException(status_code=400, detail="An API key is required.")