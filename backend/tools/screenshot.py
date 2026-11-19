"""A photo of a deployed app, taken with the Playwright its tests already use."""

import time
from pathlib import Path

from tools.commands import run_command

SCRIPT = Path(__file__).with_name("screenshot.cjs")
TIMEOUT_SECONDS = 60
# Photos are only shown while a build's job is remembered, which is until the
# server restarts, so a week is plenty.
KEEP_SECONDS = 7 * 24 * 3600


def take_screenshot(workspace: Path, url: str, out: Path) -> bool:
    """Save a JPEG of the page at url to out. False when it could not be taken."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    result = run_command(workspace, ["node", str(SCRIPT), url, str(out)], timeout=TIMEOUT_SECONDS)
    return result.ok and out.exists() and out.stat().st_size > 0


def remove_old(folder: Path, now: float | None = None) -> None:
    """Delete photos older than a week, so the folder does not grow forever."""
    now = now or time.time()
    for path in folder.glob("*.jpg"):
        try:
            if now - path.stat().st_mtime > KEEP_SECONDS:
                path.unlink()
        except OSError:
            pass
