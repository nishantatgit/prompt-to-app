"""An app's spec, kept next to its code so development can be resumed.

spec/
  README.md          what the app is, written for people
  requirements.json  the analyst's requirements, exactly as validated
  architecture.json  the architect's plan, exactly as validated
  test-plan.json     the test planner's plan, exactly as validated
  history.json       every prompt that shaped the app, oldest first

The JSON files are what a later build loads to change the app; README.md
says the same for a person reading the repo. Deploys skip the spec folder.
"""

import json
import time
from pathlib import Path

SPEC_DIR = "spec"
FILES = {
    "requirements": "requirements.json",
    "architecture": "architecture.json",
    "test_plan": "test-plan.json",
}
HISTORY = "history.json"


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_spec(job_dir: Path) -> dict | None:
    """The saved spec, or None when the folder has none."""
    folder = Path(job_dir) / SPEC_DIR
    if not folder.is_dir():
        return None
    spec = {}
    for key, name in FILES.items():
        path = folder / name
        spec[key] = json.loads(path.read_text()) if path.exists() else None
    history = folder / HISTORY
    spec["history"] = json.loads(history.read_text()) if history.exists() else []
    return spec


def write_spec(job_dir: Path, state: dict, now: float | None = None) -> None:
    """Save the job's plan, adding this prompt to the app's history."""
    folder = Path(job_dir) / SPEC_DIR
    folder.mkdir(exist_ok=True)
    history = (read_spec(job_dir) or {}).get("history", [])
    history.append(
        {
            "job_id": state.get("job_id", ""),
            "prompt": state.get("prompt", ""),
            "at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now)
            ),
            "confidence": state.get("confidence"),
        }
    )
    for key, name in FILES.items():
        if state.get(key) is not None:
            _write_json(folder / name, state[key])
    _write_json(folder / HISTORY, history)
    (folder / "README.md").write_text(readme(state, history))


def readme(state: dict, history: list[dict]) -> str:
    requirements = state.get("requirements") or {}
    architecture = state.get("architecture") or {}
    test_plan = state.get("test_plan") or {}
    lines = [f"# {requirements.get('app_summary') or 'App spec'}", ""]
    lines += ["Written by Vyskar. The JSON files next to this one are the source of truth.", ""]

    lines += ["## Prompts", ""]
    lines += [f"{i}. {h['prompt']} ({h['at'][:10]})" for i, h in enumerate(history, 1)]

    lines += ["", "## Requirements", ""]
    for r in requirements.get("requirements", []):
        lines.append(f"- **{r['id']}** ({r.get('kind', '')}): {r['statement']}")
    if requirements.get("out_of_scope"):
        lines += ["", "Out of scope: " + "; ".join(requirements["out_of_scope"])]

    lines += ["", "## Features", ""]
    for f in architecture.get("features", []):
        lines.append(f"### {f['id']}: {f['name']}")
        lines.append("")
        lines.append(f.get("description", ""))
        lines.append("")
        lines += [f"- {c['id']}: {c['statement']}" for c in f.get("acceptance_criteria", [])]
        lines.append("")

    if architecture.get("tables"):
        lines += ["## Data", ""]
        for t in architecture["tables"]:
            columns = ", ".join(c["name"] for c in t.get("columns", []))
            lines.append(f"- **{t['name']}** ({columns})")
            lines += [f"  - {rule}" for rule in t.get("access_rules", [])]
        lines.append("")

    lines += ["## Tests", ""]
    for e in test_plan.get("e2e_tests", []):
        lines.append(f"- {e['id']} ({e.get('criterion_id', '')}): {e.get('description', '')}")
    confidence = state.get("confidence")
    if confidence is not None:
        lines += ["", f"Last run: {confidence}% of tests passed."]
    return "\n".join(lines).rstrip() + "\n"


def make_save_spec():
    def save_spec(state: dict) -> dict:
        if state.get("workspace_dir"):
            write_spec(Path(state["workspace_dir"]), state)
        return {}

    return save_spec
