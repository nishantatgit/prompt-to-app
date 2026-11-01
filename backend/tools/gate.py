"""Confidence score for a build: the share of tests that passed."""


def _passed(case: dict) -> bool:
    # Supports a boolean "passed" field, or a text result such as
    # "passed" or Playwright's "expected".
    if "passed" in case:
        return bool(case["passed"])
    result = case.get("status") or case.get("outcome") or case.get("result")
    return result in ("passed", "pass", "expected")


def confidence(cases: list[dict]) -> float:
    if not cases:
        return 0.0
    passed = sum(1 for case in cases if _passed(case))
    return round(100 * passed / len(cases), 1)