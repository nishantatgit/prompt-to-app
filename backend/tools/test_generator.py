import json
from pathlib import Path

def create_test(test: dict, workspace_dir: str) -> Path:
    path = Path(workspace_dir) / "tests" / f"{test['criterion_id']}-{test['id']}.spec.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(test['code']) + "\n")
    return path