import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.llm import create_llm
from api.jobs import create_job, get_job, public_view, submit
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


@router.post("/build", status_code=202)
def build(
    req: BuildRequest,
    models: AgentModels = Depends(get_agent_models),
    limits: AgentLimits = Depends(get_agent_limits),
    settings: Settings = Depends(get_settings),
):
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
