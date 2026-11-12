"""The sandbox's file operations as LangChain tools, ready for bind_tools().

A failed call returns "Error: ..." as the tool's answer instead of raising, so
the model reads what went wrong and can try again within the same loop.
"""

from collections.abc import Callable
from functools import wraps

from langchain_core.tools import BaseTool, StructuredTool

from tools.sandbox import Sandbox, ToolError


# Keeps fn's name and signature, so LangChain builds the argument schema from it.
def _safe(fn: Callable[..., str]) -> Callable[..., str]:
    @wraps(fn)
    def call(*args, **kwargs) -> str:
        try:
            return fn(*args, **kwargs)
        except ToolError as e:
            return f"Error: {e}"

    return call


def make_file_tools(sandbox: Sandbox) -> list[BaseTool]:
    def write_file(path: str, content: str) -> str:
        return sandbox.write_file(path, content)

    def read_file(path: str) -> str:
        return sandbox.read_file(path)

    def edit_file(path: str, old: str, new: str) -> str:
        return sandbox.edit_file(path, old, new)

    def list_files() -> str:
        return sandbox.list_files()

    specs = [
        (
            write_file,
            "Create a file, or replace a whole file, in the project. Paths are relative "
            "to the project root, such as src/App.jsx. Use edit_file for small changes.",
        ),
        (read_file, "Read a file in the project, such as src/App.jsx."),
        (
            edit_file,
            "Replace one exact piece of text in a file. `old` must appear exactly once "
            "in the file; include a few surrounding lines to make it unique. Prefer this "
            "over write_file for fixes.",
        ),
        (list_files, "List the project's files, one path per line."),
    ]
    return [
        StructuredTool.from_function(func=_safe(fn), name=fn.__name__, description=description)
        for fn, description in specs
    ]
