import json

import pytest

from api import env
from api.env import env_int
from api.trial import TrialConfig


@pytest.fixture(autouse=True)
def fresh_reports():
    env._reported.clear()
    yield
    env._reported.clear()


def logged(out: str) -> list[dict]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def test_unset_uses_the_default(monkeypatch):
    monkeypatch.delenv("VYSKAR_TEST_NUMBER", raising=False)
    assert env_int("VYSKAR_TEST_NUMBER", 7) == 7


@pytest.mark.parametrize("raw, expected", [("5", 5), (" 12 ", 12), ("0", 0)])
def test_whole_numbers_are_read(monkeypatch, raw, expected):
    monkeypatch.setenv("VYSKAR_TEST_NUMBER", raw)
    assert env_int("VYSKAR_TEST_NUMBER", 7) == expected


@pytest.mark.parametrize("raw", ["", "five", "2.5", "3 builds"])
def test_a_bad_value_falls_back_and_is_logged_once(monkeypatch, capsys, raw):
    monkeypatch.setenv("VYSKAR_TEST_NUMBER", raw)
    assert env_int("VYSKAR_TEST_NUMBER", 7) == 7
    assert env_int("VYSKAR_TEST_NUMBER", 7) == 7
    events = logged(capsys.readouterr().out)
    assert len(events) == 1
    assert events[0]["event"] == "bad_setting"
    assert events[0]["name"] == "VYSKAR_TEST_NUMBER"
    assert events[0]["problem"] == "not_a_whole_number"
    assert events[0]["using"] == 7
    # The value itself is never logged, in case a secret was pasted into the wrong setting.
    assert set(events[0]) == {"event", "ts", "job_id", "name", "problem", "using"}


def test_below_the_minimum_falls_back(monkeypatch, capsys):
    monkeypatch.setenv("VYSKAR_TEST_NUMBER", "0")
    assert env_int("VYSKAR_TEST_NUMBER", 6, minimum=1) == 6
    monkeypatch.setenv("VYSKAR_TEST_NUMBER", "-3")
    assert env_int("VYSKAR_TEST_NUMBER", 2) == 2
    problems = [e["problem"] for e in logged(capsys.readouterr().out)]
    assert problems == ["below_minimum", "below_minimum"]


def test_a_typo_in_free_trial_builds_turns_the_trial_off(monkeypatch):
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "five")
    monkeypatch.setenv("FREE_TRIAL_DAILY_CAP", "")
    config = TrialConfig.from_env()
    assert not config.enabled
    assert config.daily_cap == 50
