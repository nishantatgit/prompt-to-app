from pathlib import Path

from tools.commands import run_command


def python_errors(job_dir: Path) -> str:
    """Syntax errors in the app's Python functions under api/, which the
    frontend build never looks at. Empty when there are none."""
    errors = []
    for path in sorted((job_dir / "api").rglob("*.py")):
        try:
            compile(path.read_text(), path.relative_to(job_dir).as_posix(), "exec")
        except SyntaxError as error:
            errors.append(f"{error.filename}:{error.lineno}: {error.msg}\n{error.text or ''}")
    return "\n".join(errors)


def build_check(state: dict) -> dict:
    job_dir = Path(state["workspace_dir"])

    if not (job_dir / "node_modules").exists():
        install = run_command(job_dir, ["yarn", "install"])
        if not install.ok:
            return {"build_ok": False, "build_log": "yarn install failed:\n" + install.log}

    build = run_command(job_dir, ["yarn", "build"])
    if not build.ok:
        return {"build_ok": False, "build_log": build.log}

    errors = python_errors(job_dir)
    if errors:
        return {"build_ok": False, "build_log": build.log + "\nPython syntax errors:\n" + errors}
    return {"build_ok": True, "build_log": build.log}
