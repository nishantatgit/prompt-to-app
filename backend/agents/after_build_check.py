from agents.state import JobState
from langgraph.graph import END
from typing import Literal

def make_after_build_check(max_attempts: int):
    def after_build_check(state: JobState) -> Literal["builder","write_test", "__end__"]:
        if state.get("build_ok"):
            return "write_test"                          # later: the test step
        if state.get("build_log", "").startswith("yarn install failed"):
            return END                          # environment problem, not the code
        if state.get("builder_attempts", 0) < max_attempts:
            return "builder"
        return END
    return after_build_check
