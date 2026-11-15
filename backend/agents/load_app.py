"""Load an existing app, so a build can change it instead of starting over.

Runs after the guard. For a new app it does nothing. For a change it:
- downloads the source live at the app's address, spec included, into the
  job's workspace on top of the template
- plans from the whole history: every earlier prompt plus the change, so the
  analyst and architect describe the full app, not only the change
- remembers the migrations already in the app, which ran against its
  database before and must not run again
"""

from pathlib import Path

from tools import vercel
from tools.spec import read_spec
from tools.supabase import migration_files
from tools.workspace import create_workspace

NOT_SET_UP = "Changing an app needs VERCEL_TOKEN, and it is not set."
NOT_FOUND = "There is no live app named {name} to change."
NO_SPEC = (
    "{name} was built before Vyskar saved specs with apps, so it cannot be "
    "changed. Build it again to make it changeable."
)


def planning_prompt(history: list[dict], change: str) -> str:
    """Earlier prompts, oldest first, then the change. Explicit requirements
    must quote this text, so earlier prompts stay quotable."""
    earlier = "\n".join(f"- {h['prompt']}" for h in history if h.get("prompt"))
    return (
        "This app already exists. It was built from these requests, oldest first:\n"
        f"{earlier}\n\n"
        "Now change it as follows. The change wins where it conflicts with an "
        f"earlier request:\n{change}"
    )


def make_load_app(
    workspaces_dir: Path,
    token: str | None,
    find=vercel.production_deployment,
    download=vercel.download_source,
):
    def load_app(state: dict) -> dict:
        name = state.get("app_name")
        if not name:
            return {}
        if not token:
            return {"errors": [NOT_SET_UP]}
        try:
            deployment = find(token, name)
            if not deployment:
                return {"errors": [NOT_FOUND.format(name=name)]}
            job_dir = create_workspace(workspaces_dir, state["job_id"])
            download(token, deployment, job_dir)
        except Exception as error:
            return {"errors": [f"Could not load {name}: {error}"[:2000]]}
        spec = read_spec(job_dir)
        if not spec or not spec.get("history"):
            return {"errors": [NO_SPEC.format(name=name)]}
        change = state["prompt"]
        return {
            "workspace_dir": str(job_dir),
            "change_request": change,
            "prompt": planning_prompt(spec["history"], change),
            "applied_migrations": [p.name for p in migration_files(job_dir)],
        }

    return load_app


def after_load_app(state: dict) -> str:
    return "__end__" if state.get("errors") else "analyst"
