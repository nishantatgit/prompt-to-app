MIN_P3_RATE = 0.8
MIN_PASS_RATE = 0.8  # fallback when criteria have no priority yet


def _rate(cases: list[dict]) -> float:
    return sum(c["ok"] for c in cases) / len(cases) if cases else 1.0


def confidence(cases: list[dict]) -> float:
    if not cases:
        return 0.0
    passed = sum(1 for case in cases if case["status"] == "passed")
    return round(100 * passed / len(cases), 1)
