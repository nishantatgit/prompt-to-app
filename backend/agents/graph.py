from langgraph.graph import START, END, MessagesState, StateGraph
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel
from typing import Literal, TypedDict

from .guard import make_guard
from .planner import make_planner


@dataclass
class AgentModels:
    guard: BaseChatModel
    planner: BaseChatModel
    builder: BaseChatModel
    validator: BaseChatModel


@dataclass(frozen=True)
class AgentLimits:
    planner_max_attempts: int
    builder_max_attempts: int
    validator_max_attempts: int

    def __post_init__(self):
        for name, value in vars(self).items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1, got {value}")


class JobState(TypedDict, total=False):
    prompt: str
    allowed: bool
    guard_category: str
    guard_reason: str
    job_id: str
    plan: dict
    planner_attempts: int
    planner_feedback: str

    errors: list[str]


initial_state = {}


def after_guard(state: JobState):
    print()
    print("""conditional node called state["allowed"] """, state["allowed"])
    return "planner" if state["allowed"] else END


def make_after_planner(max_attempts: int):
    def after_planner(state: JobState) -> Literal["planner", "__end__"]:
        if state.get("plan"):
            return END
        if state.get("planner_attempts", 0) < max_attempts:
            return "planner"
        return END

    return after_planner


def build_graph(models: AgentModels, limits: AgentLimits):
    graph = StateGraph(JobState)

    graph.add_node("guard", make_guard(models.guard))
    graph.add_node("planner", make_planner(models.planner))

    graph.add_edge(START, "guard")
    graph.add_edge("guard", "planner")
    graph.add_conditional_edges("planner", make_after_planner(limits.planner_max_attempts))
    graph.add_edge("planner", END)

    return graph.compile()
