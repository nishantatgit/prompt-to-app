from pathlib import Path

from tools.workspace import create_workspace


def make_setup_workspace(workspaces_dir: Path):
    def setup_workspace(state: dict) -> dict:
        job_dir = create_workspace(workspaces_dir, state["job_id"])
        return {"workspace_dir": str(job_dir)}

    return setup_workspace
