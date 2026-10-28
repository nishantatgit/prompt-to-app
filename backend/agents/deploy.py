import re
from pathlib import Path

from tools.vercel import deploy_app

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
    """A readable, unique subdomain such as 'unit-converter-distances-b6527c'."""
    summary = (state.get("requirements") or {}).get("app_summary", "")
    words = [w for w in re.findall(r"[a-z0-9]+", summary.lower()) if w not in STOP_WORDS][:3]
    suffix = state["job_id"].rsplit("-", 1)[-1][:6]
    return "-".join((words or ["app"]) + [suffix])[:50]


def make_deploy(token: str | None):
    def deploy(state: dict) -> dict:
        try:
            url = deploy_app(token, Path(state["workspace_dir"]), app_name(state))
            return {"deploy_url": url, "deploy_error": ""}
        except Exception as error:
            return {"deploy_url": "", "deploy_error": str(error)[:2000]}

    return deploy
