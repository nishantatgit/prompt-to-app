from langgraph.graph import START, END, MessageState, StateGraph
from dataclasses import dataclass
from langchain_core.language_models import BaseChatModel

from guard import make_guard

@dataclass
class AgentModels:
    guard: BaseChatModel
    planner: BaseChatModel
    builder: BaseChatModel
    validator: BaseChatModel


initial_state = {}


def build_graph(models: AgentModels):
    graph = StateGraph(initial_state)
    guard = make_guard("guard", make_guard(models.guard))

    graph.add_edge(START, guard)
    graph.add_edge(END, guard)

    return graph.compile()
    

