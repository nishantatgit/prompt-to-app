import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

PROMPT = (Path(__file__).parent / "prompts" / "builder.md").read_text()


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip() + "\n"


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def make_builder(llm):
    def builder(state: dict) -> dict:
        attempts = state.get("builder_attempts", 0) + 1
        app_file = Path(state["workspace_dir"]) / "src" / "App.jsx"

        architecture = json.dumps(state["architecture"], indent=2)
        content = f"<architecture>\n{architecture}\n</architecture>"

        if attempts > 1:
            content += (
                f"\n\n<current_file>\n{app_file.read_text()}\n</current_file>"
                f"\n\n<build_log>\n{state['build_log']}\n</build_log>"
                "\n\nThe build failed. Find the cause in the build log, fix it with the "
                "smallest change, and return the complete corrected src/App.jsx."
            )

        messages = [
            SystemMessage(PROMPT),
            HumanMessage(content),
        ]
        response = llm.invoke(messages)

        app_file = Path(state["workspace_dir"]) / "src" / "App.jsx"
        app_file.write_text(strip_fences(message_text(response.content)))
        return {"files_written": ["src/App.jsx"], "builder_attempts": attempts}

    return builder
