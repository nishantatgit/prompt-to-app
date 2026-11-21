from agents.keys import KeyRejected
from api.server_key import CHECK_SECONDS, ServerKeyStatus


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_a_missing_key_is_paused_without_calling_anthropic():
    status = ServerKeyStatus(check=lambda p, k: (_ for _ in ()).throw(AssertionError()))
    assert status.paused_reason("anthropic", None) == "key_missing"
    assert status.paused_reason("anthropic", "") == "key_missing"


def test_the_answer_is_remembered_then_checked_again():
    clock, answers, calls = Clock(), ["rejected", None], []

    def check(provider, key):
        calls.append(key)
        reason = answers.pop(0)
        if reason:
            raise KeyRejected("x", reason=reason)

    status = ServerKeyStatus(check=check, clock=clock)
    assert status.paused_reason("anthropic", "k") == "rejected"
    clock.now += CHECK_SECONDS - 1
    assert status.paused_reason("anthropic", "k") == "rejected"
    assert len(calls) == 1
    clock.now += 2
    assert status.paused_reason("anthropic", "k") is None  # the key was fixed
    assert len(calls) == 2


def test_an_outage_is_not_a_pause():
    # check_key returns quietly on timeouts and outages: builds go ahead.
    status = ServerKeyStatus(check=lambda p, k: None)
    assert status.paused_reason("anthropic", "k") is None


def test_a_recorded_build_result_counts_as_a_check():
    calls = []
    status = ServerKeyStatus(check=lambda p, k: calls.append(k))
    status.record("no_credit")
    assert status.paused_reason("anthropic", "k") == "no_credit"
    assert calls == []
