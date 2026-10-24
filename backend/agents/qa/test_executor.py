import json
from pathlib import Path

from tools.commands import run_command
from tools.test_report import ANSI_CODES, free_port, parse_results, summarize

RESULTS_FILE = "playwright-results.json"
REPORT_FILE = "test-report.json"


def test_executor(state: dict) -> dict:
    job_dir = Path(state["workspace_dir"])
    results_path = job_dir / RESULTS_FILE
    results_path.unlink(missing_ok=True)

    port = free_port()
    run = run_command(job_dir, ["yarn", "playwright", "test"], timeout=600, env={"PORT": str(port)})

    if not results_path.exists():
        return {
            "tests_ok": False,
            "test_summary": "Tests did not run.\n" + run.log[-2000:],
            "test_report_path": "",
        }

    raw = json.loads(results_path.read_text())
    cases = parse_results(raw)
    context = requirement_context(state["architecture"], state["requirements"])
    for case in cases:
        case.update(context.get(case["criterion_id"], {}))
    run_errors = [ANSI_CODES.sub("", e.get("message", "")) for e in raw.get("errors", [])]

    report_path = job_dir / REPORT_FILE
    report_path.write_text(json.dumps({
        "passed": sum(c["ok"] for c in cases),
        "total": len(cases),
        "cases": cases,
        "run_errors": run_errors,
    }, indent=2))

    return {
        "tests_ok": bool(cases) and all(c["ok"] for c in cases) and not run_errors,
        "test_summary": summarize(cases, run_errors),
        "test_report_path": str(report_path),
    }

def requirement_context(architecture: dict, requirements: dict) -> dict:
    statements = {r["id"]: r["statement"] for r in requirements["requirements"]}
    index = {}
    for feature in architecture["features"]:
        for c in feature["acceptance_criteria"]:
            index[c["id"]] = {
                "criterion": c.get("statement") or c.get("description"),
                "requirements": [
                    {"id": rid, "statement": statements.get(rid)}
                    for rid in feature["requirement_ids"]
                ],
            }
    return index