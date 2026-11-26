import os
import shutil
import signal
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
    full_env = safe_env(env)
    program = shutil.which(args[0], path=full_env.get("PATH"))
    if program is None:
        raise FileNotFoundError(f"{args[0]} not found on PATH")
    args = [program, *args[1:]]
    # Its own process group, so a timeout can stop everything it started:
    # yarn runs Playwright, which runs a browser and the app's preview server.
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=full_env,
        start_new_session=os.name == "posix",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_all(process)
        stdout, stderr = _output_after_stop(process)
        log = (stdout + "\n" + stderr).strip()
        # The note goes last, so trimming the log to its end keeps it.
        note = f"{' '.join(args)} timed out after {timeout}s"
        return CommandResult(ok=False, log=(log + "\n" + note).strip()[-MAX_LOG_CHARS:])

    log = (stdout + "\n" + stderr).strip()
    return CommandResult(ok=process.returncode == 0, log=log[-MAX_LOG_CHARS:])


def _stop_all(process: subprocess.Popen) -> None:
    """Kill the command and every process it started. Killing only the
    command left them running on the server, holding memory and ports."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()


def _output_after_stop(process: subprocess.Popen) -> tuple[str, str]:
    """What the command printed before it was stopped. A process that left
    the group could still hold the pipes open, so this waits a few seconds
    at most."""
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return "", ""
