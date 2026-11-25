from pathlib import Path

from api.events import log_event
from tools.screenshot import remove_old, take_screenshot


def make_screenshot(folder: Path | None, take=take_screenshot):
    """After deploy, a photo of the live app for the end of the build
    animation. A build never fails because of it: no photo just means the
    animation ends on its drawing. folder None turns it off. A live app with
    no photo is logged as screenshot_missed, so it shows up in Fly's logs."""

    def screenshot(state: dict) -> dict:
        url = state.get("deploy_url")
        workspace = state.get("workspace_dir")
        if folder is None or not url or not workspace:
            return {}
        out = Path(folder) / f"{state['job_id']}.jpg"
        try:
            remove_old(Path(folder))
            if take(Path(workspace), url, out):
                return {"screenshot_path": str(out)}
            log_event("screenshot_missed", state["job_id"], reason="failed")
        except Exception as error:
            log_event(
                "screenshot_missed", state["job_id"], reason="error", error=type(error).__name__
            )
        return {}

    return screenshot
