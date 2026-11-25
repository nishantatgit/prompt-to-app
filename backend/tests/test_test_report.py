"""Reading Playwright's JSON report into test cases and a summary.

The report shapes below are what Playwright writes: a run stopped by the
globalTimeout reports the test it cut off, and the tests it never reached,
as skipped with "ok": true.
"""

from tools import gate
from tools.test_report import NOT_RUN, SKIPPED, parse_results, short_error, summarize


def spec(title, ok, status, expected="passed", results=(), file="F1-AC1-E1.spec.js"):
    return {
        "title": title,
        "ok": ok,
        "file": file,
        "tests": [
            {
                "expectedStatus": expected,
                "status": status,
                "results": [dict(r) for r in results],
            }
        ],
    }


def report(*specs, errors=()):
    return {"suites": [{"specs": list(specs), "suites": []}], "errors": list(errors)}


PASSED = {"status": "passed", "attachments": []}


def test_passed_test_is_ok():
    [case] = parse_results(report(spec("adds a task", True, "expected", results=[PASSED])))
    assert case == {
        "criterion_id": "F1-AC1",
        "title": "adds a task",
        "ok": True,
        "error": "",
        "trace": None,
    }


def test_flaky_test_that_passed_on_retry_is_ok():
    results = [{"status": "failed", "error": {"message": "x"}}, PASSED]
    [case] = parse_results(report(spec("t", True, "flaky", results=results)))
    assert case["ok"] is True


def test_failed_test_keeps_its_error_without_colors():
    failed = {
        "status": "failed",
        "error": {"message": "\x1b[31mexpect(locator).toBeVisible()\x1b[39m\nLocator: #save"},
        "attachments": [{"name": "trace", "path": "/w/trace.zip"}],
    }
    [case] = parse_results(report(spec("t", False, "unexpected", results=[failed])))
    assert case["ok"] is False
    assert case["error"] == "expect(locator).toBeVisible()\nLocator: #save"
    assert case["trace"] == "/w/trace.zip"


def test_tests_cut_off_by_the_time_limit_are_not_passed():
    raw = report(
        spec("quick", True, "expected", results=[PASSED]),
        # Running when the globalTimeout hit.
        spec("slow", True, "skipped", results=[{"status": "skipped"}]),
        # Never started.
        spec("never reached", True, "skipped", results=[]),
        errors=[{"message": "Timed out waiting 480s for the test suite to run"}],
    )
    cases = parse_results(raw)
    assert [c["ok"] for c in cases] == [True, False, False]
    assert [c["error"] for c in cases[1:]] == [NOT_RUN, NOT_RUN]
    # Was 100 before: Playwright calls all three "ok".
    assert gate.confidence(cases) == 33.3


def test_test_that_skips_itself_is_not_passed():
    skipped = spec("t", True, "skipped", expected="skipped", results=[{"status": "skipped"}])
    [case] = parse_results(report(skipped))
    assert case["ok"] is False
    assert case["error"] == SKIPPED


def test_specs_in_nested_suites_are_found():
    raw = {
        "suites": [
            {
                "specs": [],
                "suites": [{"specs": [spec("inner", True, "expected", results=[PASSED])]}],
            }
        ]
    }
    assert [c["title"] for c in parse_results(raw)] == ["inner"]


def test_summary_says_which_tests_did_not_run_apart_from_failures():
    cases = [
        {"criterion_id": "F1-AC1", "ok": True, "error": ""},
        {"criterion_id": "F1-AC2", "ok": False, "error": "button not found\nat line 3"},
        {"criterion_id": "F2-AC1", "ok": False, "error": NOT_RUN},
        {"criterion_id": "F2-AC2", "ok": False, "error": SKIPPED},
    ]
    assert summarize(cases, ["Timed out waiting 480s\nmore"]).splitlines() == [
        "1/4 tests passed.",
        "F1-AC2 failed: button not found",
        f"F2-AC1: {NOT_RUN}",
        f"F2-AC2: {SKIPPED}",
        "Run error: Timed out waiting 480s",
    ]


def test_short_error_keeps_the_first_line_and_the_locator_lines():
    error = "Timed out 5000ms\n\n  Locator: #add\n  Expected: visible\n  Received: hidden\n  at x"
    assert short_error(error) == (
        "Timed out 5000ms | Locator: #add | Expected: visible | Received: hidden"
    )
    assert short_error("") == "no error message"
