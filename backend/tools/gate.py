"""Confidence score for a build: the share of tests that passed."""


def _passed(case: dict) -> bool:
    # Supports a boolean "ok" field (what parse_results writes) or "passed",
    # or a text result such as "passed" or Playwright's "expected".
    if "ok" in case:
        return bool(case["ok"])
    if "passed" in case:
        return bool(case["passed"])
    result = case.get("status") or case.get("outcome") or case.get("result")
    return result in ("passed", "pass", "expected")


def confidence(cases: list[dict]) -> float:
    if not cases:
        return 0.0
    passed = sum(1 for case in cases if _passed(case))
    return round(100 * passed / len(cases), 1)


def percent_text(value: float | int) -> str:
    """A confidence as people read it: 100.0 becomes "100", 87.5 stays "87.5".
    confidence() returns a float, and Python prints 100.0 as "100.0", while
    the app (JavaScript) shows the same number as "100"."""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)
