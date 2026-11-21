import shutil
import uuid
from datetime import datetime
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "react-vite"


IGNORE = shutil.ignore_patterns(
    "node_modules", "dist", "test-results", "playwright-report", "playwright-results.json"
)


def create_workspace(workspaces_dir: Path, job_id: str) -> Path:
    job_dir = (Path(workspaces_dir) / job_id).resolve()
    shutil.copytree(TEMPLATE_DIR, job_dir, ignore=IGNORE)
    return job_dir


def new_job_id() -> str:
    now = datetime.now()
    return f"{now:%y-%m-%d}-{int(now.timestamp())}-{uuid.uuid4().hex[:10]}"


# What a build leaves in its folder that can be made again from the source:
# installed packages, the built site and Playwright's results. node_modules
# alone is well over 100 MB per build, and the folders live on Fly's 1 GB
# volume next to the credits database, so they go once the build is over.
BUILD_OUTPUT = ("node_modules", "dist", "test-results", "playwright-report")


def remove_build_output(job_dir: Path) -> None:
    """Delete a finished build's packages and outputs, keeping its source."""
    for name in BUILD_OUTPUT:
        path = Path(job_dir) / name
        if path.is_symlink():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def sweep_build_output(workspaces_dir: Path, is_active) -> list[str]:
    """remove_build_output for every job folder whose job is not running,
    including ones left from before a restart. is_active(job_id) says whether
    a job is still running. Returns the job ids cleaned."""
    root = Path(workspaces_dir)
    if not root.is_dir():
        return []
    cleaned = []
    for job_dir in sorted(root.iterdir()):
        if not job_dir.is_dir() or job_dir.is_symlink() or is_active(job_dir.name):
            continue
        if any((job_dir / name).exists() or (job_dir / name).is_symlink() for name in BUILD_OUTPUT):
            remove_build_output(job_dir)
            cleaned.append(job_dir.name)
    return cleaned
