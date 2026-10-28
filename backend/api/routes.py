import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.llm import create_llm
from agents.model_choices import MODEL_CHOICES
from api.jobs import create_job, get_job, public_view, submit
from config import Settings, get_settings
from tools.workspace import new_job_id

router = APIRouter(prefix="/api")


class BuildRequest(BaseModel):
    prompt: str
    provider: Literal["anthropic", "openai"]
    api_key: SecretStr | None = None


def make_models(provider: str, api_key: str) -> AgentModels:
    choice = MODEL_CHOICES[provider]

    def llm(agent: str):
        return create_llm(provider, choice[agent], api_key)

    return AgentModels(
        guard=llm("guard"),
        analyst=llm("analyst"),
        architect=llm("architect"),
        test_planner=llm("test_planner"),
        builder=llm("builder"),
        validator=llm("validator"),
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

    models = make_models(req.provider, key)
    graph = build_graph(
        models, limits, settings.workspaces_dir, vercel_token=os.environ.get("VERCEL_TOKEN")
    )
    job_id = new_job_id()
    create_job(job_id, req.prompt)
    submit(graph, job_id, req.prompt, settings.graph_recursion_limit)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return public_view(job)
