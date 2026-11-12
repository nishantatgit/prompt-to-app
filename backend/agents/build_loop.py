"""The build loop: one model works on the app's files with tools until it says
it is done, and the build decides whether it may stop.

The model chooses its own steps. The harness enforces two rules it cannot talk
its way past: the loop only ends on a passing build, or when a limit is hit
(build attempts or model turns).
"""

import json
from collections.abc import Callable
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.build_check import build_check
from tools.file_tools import make_file_tools
from tools.sandbox import Sandbox

PROMPTS = Path(__file__).parent / "prompts"
PROMPT = "".join(
    (PROMPTS / name).read_text() for name in ("build_loop.md", "builder.md", "design_building.md")
)

# Only the end of a build log goes back to the model; errors are printed last.
LOG_CHARS = 4000
WRITE_TOOLS = {"write_file", "edit_file"}


def make_build_loop(
    llm,
    max_builds: int = 3,
    max_turns: int = 40,
    build: Callable[[dict], dict] = build_check,
):
    def build_loop(state: dict) -> dict:
        sandbox = Sandbox(Path(state["workspace_dir"]))
        tools = {tool.name: tool for tool in make_file_tools(sandbox)}
        model = llm.bind_tools(list(tools.values()))

        architecture = json.dumps(state["architecture"], indent=2)
        messages = [
            SystemMessage(PROMPT),
            HumanMessage(f"<architecture>\n{architecture}\n</architecture>\n\nBuild this app."),
        ]
        written: list[str] = []
        builds = 0
        result = {"build_ok": False, "build_log": ""}

        for turn in range(1, max_turns + 1):
            response = model.invoke(messages)
            messages.append(response)

            if response.tool_calls:
                for call in response.tool_calls:
                    tool = tools.get(call["name"])
                    if tool is None:
                        messages.append(
                            ToolMessage(
                                f"Error: there is no tool named {call['name']}.",
                                tool_call_id=call["id"],
                            )
                        )
                        continue
                    messages.append(tool.invoke(call))
                    path = call["args"].get("path")
                    if call["name"] in WRITE_TOOLS and path and path not in written:
                        written.append(path)
                continue

            # No tool call: the model says it is done. The build decides.
            builds += 1
            result = build({"workspace_dir": state["workspace_dir"]})
            if result["build_ok"] or builds >= max_builds:
                return _finish(result, written, builds, turn)
            messages.append(
                HumanMessage(
                    "The build failed. Find the cause in the log, fix it with the smallest "
                    f"edit, then reply without a tool call.\n\n<build_log>\n"
                    f"{result['build_log'][-LOG_CHARS:]}\n</build_log>"
                )
            )

        log = f"Stopped after {max_turns} model turns without a passing build."
        if result["build_log"]:
            log += "\n\nLast build log:\n" + result["build_log"]
        return _finish({"build_ok": False, "build_log": log}, written, builds, max_turns)

    return build_loop


def _finish(result: dict, written: list[str], builds: int, turns: int) -> dict:
    return {
        "build_ok": result["build_ok"],
        "build_log": result["build_log"],
        "files_written": written,
        "builder_attempts": builds,
        "loop_turns": turns,
    }
