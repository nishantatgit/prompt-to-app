from tools.gate import confidence, percent_text


def test_confidence_is_the_share_of_tests_that_passed():
    cases = [
        {"ok": True},
        {"ok": True},
        {"ok": True},
        {"status": "failed"},
        {"passed": True},
        {"outcome": "expected"},
        {"result": "pass"},
        {"ok": False},
    ]
    assert confidence(cases) == 75.0
    assert confidence([]) == 0.0


def test_a_whole_percentage_reads_without_a_decimal():
    assert percent_text(100.0) == "100"
    assert percent_text(0.0) == "0"
    assert percent_text(92) == "92"


def test_a_fraction_keeps_its_decimal():
    assert percent_text(87.5) == "87.5"
    assert percent_text(confidence([{"ok": True}, {"ok": True}, {"ok": False}])) == "66.7"
