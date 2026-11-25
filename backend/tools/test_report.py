import re
import socket
from pathlib import Path

ANSI_CODES = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Playwright's report says "ok" for a skipped test too, and a test that never
# ran (the 8 minute globalTimeout stopped the run first) or was cut off midway
# is reported as skipped. Only a test whose outcome is one of these, so it ran
# to its end and did what it expected, counts as passed here: a run cut short
# can't show as "10/10 tests passed" and 100% confidence.
PASSED_OUTCOMES = ("expected", "flaky")
NOT_RUN = "Did not run: the test run stopped before this test finished."
SKIPPED = "Skipped: the test skipped itself, so nothing was checked."


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def collect_specs(suites: list[dict]):
    for suite in suites:
        yield from suite.get("specs", [])
        yield from collect_specs(suite.get("suites", []))


def parse_results(raw: dict) -> list[dict]:
    cases = []
    for spec in collect_specs(raw.get("suites", [])):
        test = spec["tests"][0] if spec["tests"] else {}
        results = test.get("results", [])
        last = results[-1] if results else {}
        ok = bool(spec["ok"]) and test.get("status") in PASSED_OUTCOMES
        error = ""
        if not spec["ok"]:
            message = (last.get("error") or {}).get("message", "")
            error = ANSI_CODES.sub("", message)[:500]
        elif not ok:
            # test.skip() and test.fixme() expect to be skipped; a test cut
            # off by the time limit expected to pass.
            error = SKIPPED if test.get("expectedStatus") == "skipped" else NOT_RUN
        file_stem = Path(spec["file"]).name.removesuffix(".spec.js")  # "F1-AC1-E1"
        cases.append(
            {
                "criterion_id": file_stem.rsplit("-", 1)[0],  # "F1-AC1"
                "title": spec["title"],
                "ok": ok,
                "error": error,
                "trace": trace_path(last),
            }
        )
    return cases


def short_error(error: str) -> str:
    lines = [line.strip() for line in error.splitlines() if line.strip()]
    if not lines:
        return "no error message"
    keep = [lines[0]] + [x for x in lines if x.startswith(("Locator:", "Expected:", "Received:"))]
    return " | ".join(keep)


def summarize(cases: list[dict], run_errors: list[str]) -> str:
    passed = sum(c["ok"] for c in cases)
    lines = [f"{passed}/{len(cases)} tests passed."]
    for c in cases:
        if c["ok"]:
            continue
        if c["error"] in (NOT_RUN, SKIPPED):  # not a failure: nothing was checked
            lines.append(f"{c['criterion_id']}: {c['error']}")
        else:
            lines.append(f"{c['criterion_id']} failed: {short_error(c['error'])}")
    for e in run_errors:
        lines.append(f"Run error: {e.splitlines()[0] if e else 'unknown'}")
    return "\n".join(lines)


def trace_path(result):
    for a in result.get("attachments", []):
        if a.get("name") == "trace" and a.get("path"):
            return a["path"]
    return None
