from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from agents.state import JobState
from agents.analyst import make_analyst
from agents.architect import make_architect
from agents.guard import make_guard
from agents.test_planner import make_test_planner
from agents.setup_workspace import make_setup_workspace
from agents.builder import make_builder
from agents.build_loop import make_build_loop
from agents.build_check import build_check
from agents.after_build_check import make_after_build_check
from agents.qa.test_writer import test_writer
from agents.qa.test_executor import test_executor
from agents.deploy import make_deploy
from agents.database import after_database, after_migrations, make_database, make_migrations


@dataclass
class AgentModels:
    guard: BaseChatModel
    analyst: BaseChatModel
    architect: BaseChatModel
    test_planner: BaseChatModel
    builder: BaseChatModel
    validator: BaseChatModel


@dataclass(frozen=True)
class AgentLimits:
    analyst_max_attempts: int
    architect_max_attempts: int
    test_planner_max_attempts: int
    builder_max_attempts: int
    validator_max_attempts: int

    def __post_init__(self):
        for name, value in vars(self).items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1, got {value}")


def after_guard(state: JobState) -> Literal["analyst", "__end__"]:
    return "analyst" if state.get("allowed", False) else END


def make_after_analyst(max_attempts: int):
    def after_analyst(state: JobState) -> Literal["architect", "analyst", "__end__"]:
        if state.get("requirements"):
            return "architect"
        if state.get("analyst_attempts", 0) < max_attempts:
            return "analyst"
        return END

    return after_analyst


def make_after_architect(max_attempts: int):
    def after_architect(state: JobState) -> Literal["setup_workspace", "architect", "__end__"]:
        if state.get("architecture"):
            return "setup_workspace"
        if state.get("architect_attempts", 0) < max_attempts:
            return "architect"
        return END

    return after_architect


def build_done(state: JobState) -> dict:
    return {}


BuilderMode = Literal["pipeline", "loop"]


def after_build_loop(state: JobState) -> Literal["migrations", "__end__"]:
    # The loop already retried inside itself, so a failure here is final.
    return "migrations" if state.get("build_ok") else END


def make_after_test_planner(max_attempts: int):
    def after_test_planner(
        state: JobState,
    ) -> Literal["write_test", "test_planner", "__end__"]:
        if state.get("test_plan"):
            return "write_test"
        if state.get("test_planner_attempts", 0) < max_attempts:
            return "test_planner"
        return END

    return after_test_planner


def build_graph(
    models: AgentModels,
    limits: AgentLimits,
    workspaces_dir: Path,
    vercel_token: str | None = None,
    builder_mode: BuilderMode = "pipeline",
    supabase_config_id: str | None = None,
    supabase_access_token: str | None = None,
):
    graph = StateGraph(JobState)

    graph.add_node("guard", make_guard(models.guard))
    graph.add_node("analyst", make_analyst(models.analyst))
    graph.add_node("architect", make_architect(models.architect))
    graph.add_node("test_planner", make_test_planner(models.test_planner))
    graph.add_node("setup_workspace", make_setup_workspace(workspaces_dir))
    # pipeline: one model call writes App.jsx, then build_check, with retries
    #           routed through the graph.
    # loop:     one node where the model works on files with tools until the
    #           build passes or a limit is hit. It keeps the name "builder" so
    #           job stages and the rest of the graph stay the same.
    if builder_mode == "loop":
        graph.add_node(
            "builder", make_build_loop(models.builder, max_builds=limits.builder_max_attempts)
        )
    else:
        graph.add_node("builder", make_builder(models.builder))
        graph.add_node("build_check", build_check)
    # Apps that store data in Supabase get a database before the build and
    # their migrations after it. Other apps pass straight through both.
    graph.add_node(
        "database",
        make_database(vercel_token, supabase_config_id, access_token=supabase_access_token),
    )
    graph.add_node("migrations", make_migrations())
    graph.add_node("build_done", build_done)
    graph.add_node("write_test", test_writer)
    graph.add_node("test_executor", test_executor)
    graph.add_node("deploy", make_deploy(vercel_token))
    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", after_guard)
    graph.add_conditional_edges("analyst", make_after_analyst(limits.analyst_max_attempts))
    graph.add_conditional_edges("architect", make_after_architect(limits.architect_max_attempts))
    graph.add_conditional_edges(
        "test_planner", make_after_test_planner(limits.test_planner_max_attempts)
    )
    graph.add_edge("setup_workspace", "database")
    graph.add_conditional_edges("database", after_database, ["builder", END])
    graph.add_edge("setup_workspace", "test_planner")
    graph.add_conditional_edges("migrations", after_migrations, ["build_done", END])

    if builder_mode == "loop":
        graph.add_conditional_edges("builder", after_build_loop)
    else:
        graph.add_edge("builder", "build_check")
        graph.add_conditional_edges(
            "build_check", make_after_build_check(limits.builder_max_attempts)
        )
    graph.add_edge(["build_done", "write_test"], "test_executor")
    # Deploy always runs; without a token it records why it skipped.
    graph.add_edge("test_executor", "deploy")
    graph.add_edge("deploy", END)
    return graph.compile()
