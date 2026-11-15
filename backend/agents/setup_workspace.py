from pathlib import Path

from tools.workspace import create_workspace


def make_setup_workspace(workspaces_dir: Path):
    def setup_workspace(state: dict) -> dict:
        if state.get("workspace_dir"):
            return {}  # load_app already put the app's code there
        job_dir = create_workspace(workspaces_dir, state["job_id"])
        return {"workspace_dir": str(job_dir)}

    return setup_workspace
