"""File tools for the build loop, confined to one job's workspace.

The model in the build loop can only change the app through these four
operations. Every path is checked to stay inside the workspace, and every
failure raises ToolError with a message written for the model, since the loop
passes it back as the tool result.
"""

from pathlib import Path

# Folders that tools never list: installed packages and build or test output.
HIDDEN = {"node_modules", "dist", "test-results", "playwright-report"}


class ToolError(Exception):
    """A tool call the model can fix. The message goes back to the model."""


class Sandbox:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace does not exist: {self.root}")

    def _resolve(self, path: str) -> Path:
        full = (self.root / path).resolve()
        if not full.is_relative_to(self.root):
            raise ToolError(f"Path '{path}' is outside the project.")
        return full

    def write_file(self, path: str, content: str) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        return f"Wrote {path} ({len(content)} characters)."

    def read_file(self, path: str) -> str:
        full = self._resolve(path)
        if not full.is_file():
            raise ToolError(f"File '{path}' does not exist.")
        return full.read_text()

    def edit_file(self, path: str, old: str, new: str) -> str:
        text = self.read_file(path)
        count = text.count(old)
        if count == 0:
            raise ToolError(f"The text to replace was not found in {path}.")
        if count > 1:
            raise ToolError(
                f"The text to replace appears {count} times in {path}. "
                "Include more surrounding lines so it is unique."
            )
        self._resolve(path).write_text(text.replace(old, new, 1))
        return f"Edited {path}."

    def list_files(self) -> str:
        files = sorted(
            str(p.relative_to(self.root))
            for p in self.root.rglob("*")
            if p.is_file() and not HIDDEN.intersection(p.relative_to(self.root).parts)
        )
        return "\n".join(files) or "(empty project)"
