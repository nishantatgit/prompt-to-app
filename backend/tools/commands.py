import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_LOG_CHARS = 6000


@dataclass
class CommandResult:
    ok: bool
    log: str


def run_command(cwd: Path, args: list[str], timeout: int = 300) -> CommandResult:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return CommandResult(ok=False, log=f"{' '.join(args)} timed out after {timeout}s")

    log = (result.stdout + "\n" + result.stderr).strip()
    return CommandResult(ok=result.returncode == 0, log=log[-MAX_LOG_CHARS:])
