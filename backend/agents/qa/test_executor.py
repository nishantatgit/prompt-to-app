import json
from pathlib import Path

from agents.database import DATABASE_ENV
from tools import gate, test_data
from tools.commands import run_command
from tools.test_report import ANSI_CODES, free_port, parse_results, summarize

RESULTS_FILE = "playwright-results.json"
REPORT_FILE = "test-report.json"

NOT_RESTORED = (
    "The tests' data couldn't be removed from the app's database, so the app "
    "was not put online with it. Build again in a minute. ({error})"
)


def test_executor(state: dict) -> dict:
    """Run the tests. For an app with a database, the tests use the app's
    real database, so it is saved before them and put back after (see
    tools/test_data.py): people never see the tests' rows or users."""
    url_file = Path(state["workspace_dir"]) / DATABASE_ENV
    database_url = url_file.read_text().strip() if url_file.exists() else ""
    if not database_url:
        return run_tests(state)
    try:
        test_data.snapshot(database_url)
    except Exception as error:
        # Without a snapshot the tests would leave their rows behind, so they
        # don't run. The app still goes online, marked as untested.
        summary = f"Tests did not run: the app's database couldn't be saved first. {error}"
        return {"tests_ok": False, "test_summary": summary[:2000], "test_report_path": ""}
    try:
        result = run_tests(state)
    finally:
        try:
            test_data.restore(database_url)
            restore_error = ""
        except Exception as error:
            restore_error = NOT_RESTORED.format(error=str(error)[:500])
    if restore_error:
        return {**result, "tests_ok": False, "test_data_error": restore_error}
    return result


def run_tests(state: dict) -> dict:
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
    report_path.write_text(
        json.dumps(
            {
                "passed": sum(c["ok"] for c in cases),
                "total": len(cases),
                "cases": cases,
                "run_errors": run_errors,
            },
            indent=2,
        )
    )

    return {
        "tests_ok": bool(cases) and all(c["ok"] for c in cases) and not run_errors,
        "test_summary": summarize(cases, run_errors),
        "test_report_path": str(report_path),
        "confidence": gate.confidence(cases),
    }


def requirement_context(architecture: dict, requirements: dict) -> dict:
    statements = {r["id"]: r["statement"] for r in requirements["requirements"]}
    index = {}
    for feature in architecture["features"]:
        for c in feature["acceptance_criteria"]:
            index[c["id"]] = {
                "criterion": c.get("statement") or c.get("description"),
                "priority": c.get("priority"),
                "requirements": [
                    {"id": rid, "statement": statements.get(rid)}
                    for rid in feature["requirement_ids"]
                ],
            }
    return index
