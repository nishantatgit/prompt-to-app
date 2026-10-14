from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agents.graph import AgentModels, build_graph
from agents.llm import create_llm
from config import Settings, get_settings

router = APIRouter(prefix="/api")


class BuildRequest(BaseModel):
    prompt: str


def get_agent_models(settings: Settings = Depends(get_settings)) -> AgentModels:
    def llm(provider, model):
        return create_llm(provider, model, settings.api_key_for(provider))

    return AgentModels(
        guard=llm(settings.guard_provider, settings.guard_model),
        planner=llm(settings.planner_provider, settings.planner_model),
        builder=llm(settings.builder_provider, settings.builder_model),
        validator=llm(settings.validator_provider, settings.validator_model),
    )


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/build")
def build(req: BuildRequest, models: AgentModels = Depends(get_agent_models)):
    graph = build_graph(models)
    result = graph.invoke({"prompt": req.prompt})
    return result