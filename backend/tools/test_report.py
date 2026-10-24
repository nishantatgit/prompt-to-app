import re
import socket
from pathlib import Path

ANSI_CODES = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


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
        results = spec["tests"][0]["results"] if spec["tests"] else []
        last = results[-1] if results else {}
        error = ""
        if not spec["ok"]:
            message = (last.get("error") or {}).get("message", "")
            error = ANSI_CODES.sub("", message)[:500]
        file_stem = Path(spec["file"]).name.removesuffix(".spec.js")  # "F1-AC1-E1"
        cases.append({
            "criterion_id": file_stem.rsplit("-", 1)[0],                # "F1-AC1"
            "title": spec["title"],
            "ok": spec["ok"],
            "error": error,
            "trace": trace_path(last),
        })
    return cases

def short_error(error: str) -> str:
    lines = [l.strip() for l in error.splitlines() if l.strip()]
    if not lines:
        return "no error message"
    keep = [lines[0]] + [l for l in lines if l.startswith(("Locator:", "Expected:", "Received:"))]
    return " | ".join(keep)


def summarize(cases: list[dict], run_errors: list[str]) -> str:
    passed = sum(c["ok"] for c in cases)
    lines = [f"{passed}/{len(cases)} tests passed."]
    for c in cases:
        if not c["ok"]:
            lines.append(f"{c['criterion_id']} failed: {short_error(c['error'])}")
    for e in run_errors:
        lines.append(f"Run error: {e.splitlines()[0] if e else 'unknown'}")
    return "\n".join(lines)

def trace_path(result):
    for a in result.get("attachments", []):
        attachment_name = a.get("name")
        print("attachment_name : ", attachment_name)
        if attachment_name == "trace" and a.get("path"):
            return a["path"]
    return None