import uuid
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.llm import create_llm
from config import Settings, get_settings

from tools.workspace import new_job_id

router = APIRouter(prefix="/api")


class BuildRequest(BaseModel):
    prompt: str


def get_agent_models(settings: Settings = Depends(get_settings)) -> AgentModels:
    def llm(provider, model):
        return create_llm(provider, model, settings.api_key_for(provider))

    return AgentModels(
        guard=llm(settings.guard_provider, settings.guard_model),
        analyst=llm(settings.guard_provider, settings.guard_model),
        architect=llm(settings.architect_provider, settings.architect_model),
        test_planner=llm(settings.test_planner_provider, settings.test_planner_model),
        builder=llm(settings.builder_provider, settings.builder_model),
        validator=llm(settings.validator_provider, settings.validator_model),
    )


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


@router.post("/build")
def build(
    req: BuildRequest,
    models: AgentModels = Depends(get_agent_models),
    limits: AgentLimits = Depends(get_agent_limits),
    settings: Settings = Depends(get_settings),
):
    graph = build_graph(
        models, limits, settings.workspaces_dir, vercel_token=os.environ.get("VERCEL_TOKEN")
    )
    result = graph.invoke(
        {"prompt": req.prompt, "job_id": new_job_id()},
        {"recursion_limit": settings.graph_recursion_limit},
    )
    return result
