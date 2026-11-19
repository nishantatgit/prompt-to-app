from pathlib import Path

from tools.screenshot import remove_old, take_screenshot


def make_screenshot(folder: Path | None, take=take_screenshot):
    """After deploy, a photo of the live app for the end of the build
    animation. A build never fails because of it: no photo just means the
    animation ends on its drawing. folder None turns it off."""

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
        except Exception:
            pass
        return {}

    return screenshot
