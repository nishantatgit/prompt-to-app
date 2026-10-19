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
