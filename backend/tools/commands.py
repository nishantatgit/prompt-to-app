import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_LOG_CHARS = 6000

# The only variables generated code may see. Secrets such as VERCEL_TOKEN,
# LANGSMITH_API_KEY or LLM keys are never passed to yarn, vite or Playwright.
SAFE_ENV_VARS = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "PLAYWRIGHT_BROWSERS_PATH",
    "SYSTEMROOT",
    "PATHEXT",
    "COMSPEC",
    "APPDATA",
    "LOCALAPPDATA",
    "USERPROFILE",
    "TEMP",
    "TMP",
)


@dataclass
class CommandResult:
    ok: bool
    log: str


def safe_env(extra: dict | None = None) -> dict:
    env = {name: os.environ[name] for name in SAFE_ENV_VARS if name in os.environ}
    env.update(extra or {})
    return env


def run_command(
    cwd: Path, args: list[str], timeout: int = 300, env: dict | None = None
) -> CommandResult:
    try:
        full_env = safe_env(env)
        program = shutil.which(args[0], path=full_env.get("PATH"))
        if program is None:
            raise FileNotFoundError(f"{args[0]} not found on PATH")
        args = [program, *args[1:]]
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=safe_env(env),
        )
    except subprocess.TimeoutExpired:
        return CommandResult(ok=False, log=f"{' '.join(args)} timed out after {timeout}s")

    log = (result.stdout + "\n" + result.stderr).strip()
    return CommandResult(ok=result.returncode == 0, log=log[-MAX_LOG_CHARS:])
