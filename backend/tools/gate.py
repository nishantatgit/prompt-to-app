MIN_P3_RATE = 0.8
MIN_PASS_RATE = 0.8  # fallback when criteria have no priority yet


def _rate(cases: list[dict]) -> float:
    return sum(c["ok"] for c in cases) / len(cases) if cases else 1.0


def gate(cases: list[dict]) -> tuple[bool, str]:
    if not cases:
        return False, "no tests ran"

    if not any(c.get("priority") for c in cases):
        rate = _rate(cases)
        return rate >= MIN_PASS_RATE, f"{rate:.0%} of tests passed (need {MIN_PASS_RATE:.0%})"

    must_pass = [c for c in cases if c.get("priority") in ("P1", "P2") and not c["ok"]]
    if must_pass:
        ids = ", ".join(c["criterion_id"] for c in must_pass)
        return False, f"P1/P2 failed: {ids}"

    p3 = [c for c in cases if c.get("priority") == "P3"]
    rate = _rate(p3)
    if rate < MIN_P3_RATE:
        return False, f"P3 pass rate {rate:.0%} (need {MIN_P3_RATE:.0%})"
    return True, "all P1/P2 passed, P3 above threshold"