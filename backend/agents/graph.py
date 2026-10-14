from langgraph.graph import START, END, MessagesState, StateGraph
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from typing import TypedDict

from .guard import make_guard

@dataclass
class AgentModels:
    guard: BaseChatModel
    planner: BaseChatModel
    builder: BaseChatModel
    validator: BaseChatModel

class JobState(TypedDict, total=False):
    prompt: str
    allowed: bool
    guard_category: str
    guard_reason: str
    plan: dict
    errors: list[str]
    attempts: int

initial_state = {}


def build_graph(models: AgentModels):
    graph = StateGraph(JobState)
    
    graph.add_node("guard",  make_guard(models.guard))
    graph.add_edge(START, "guard")
    graph.add_edge("guard", END)

    return graph.compile()
    

