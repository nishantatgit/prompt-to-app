from pathlib import Path

from tools.commands import run_command


def build_check(state: dict) -> dict:
    job_dir = Path(state["workspace_dir"])

    if not (job_dir / "node_modules").exists():
        install = run_command(job_dir, ["yarn", "install"])
        if not install.ok:
            return {"build_ok": False, "build_log": "yarn install failed:\n" + install.log}

    build = run_command(job_dir, ["yarn", "build"])
    return {"build_ok": build.ok, "build_log": build.log}
