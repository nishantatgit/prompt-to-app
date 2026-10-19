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