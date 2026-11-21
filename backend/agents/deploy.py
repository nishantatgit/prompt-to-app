import re
from pathlib import Path

from tools.edit_key import ENV_KEY
from tools.vercel import deploy_app, set_project_env

STOP_WORDS = {
    "a",
    "an",
    "the",
    "for",
    "and",
    "of",
    "to",
    "with",
    "that",
    "where",
    "which",
    "my",
    "users",
    "user",
}


def app_name(state: dict) -> str:
    """A readable, unique subdomain such as 'unit-converter-distances-b6527c'.
    A change to an existing app keeps that app's name."""
    if state.get("app_name"):
        return state["app_name"]
    summary = (state.get("requirements") or {}).get("app_summary", "")
    words = [w for w in re.findall(r"[a-z0-9]+", summary.lower()) if w not in STOP_WORDS][:3]
    suffix = state["job_id"].rsplit("-", 1)[-1][:6]
    return "-".join((words or ["app"]) + [suffix])[:50]


NO_TOKEN = "Deploy skipped: VERCEL_TOKEN is not set. The app was built and tested."


def make_deploy(token: str | None, set_env=set_project_env):
    def deploy(state: dict) -> dict:
        if state.get("test_data_error"):
            return {"deploy_url": "", "deploy_error": state["test_data_error"]}
        if not token:
            return {"deploy_url": "", "deploy_error": NO_TOKEN}
        name = app_name(state)
        try:
            url = deploy_app(token, Path(state["workspace_dir"]), name)
        except Exception as error:
            return {"deploy_url": "", "deploy_error": str(error)[:2000]}
        out = {"deploy_url": url, "deploy_error": "", "deployed_name": name}
        # A new app remembers who may change it. A changed app keeps its key.
        if state.get("edit_key_hash") and not state.get("app_name"):
            try:
                set_env(token, name, ENV_KEY, state["edit_key_hash"])
                out["editable"] = True
            except Exception:
                out["editable"] = False  # the app works; it just cannot be changed later
        elif state.get("app_name"):
            out["editable"] = True
        return out

    return deploy
