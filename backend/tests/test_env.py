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


# On/off settings: every spelling of on and off reads the same, so
# ALLOW_OWN_KEYS=0 really turns own keys off.


@pytest.mark.parametrize("raw", ["true", "True", "TRUE", " true ", "1", "yes", "on", "On\n"])
def test_on_words_turn_a_flag_on(monkeypatch, raw):
    monkeypatch.setenv("VYSKAR_TEST_FLAG", raw)
    assert env.env_flag("VYSKAR_TEST_FLAG", False) is True


@pytest.mark.parametrize("raw", ["false", "False", "FALSE", "false ", "0", "no", "off", "Off\n"])
def test_off_words_turn_a_flag_off(monkeypatch, raw):
    monkeypatch.setenv("VYSKAR_TEST_FLAG", raw)
    assert env.env_flag("VYSKAR_TEST_FLAG", True) is False


@pytest.mark.parametrize("default", [True, False])
def test_unset_or_blank_flag_uses_the_default(monkeypatch, capsys, default):
    monkeypatch.delenv("VYSKAR_TEST_FLAG", raising=False)
    assert env.env_flag("VYSKAR_TEST_FLAG", default) is default
    monkeypatch.setenv("VYSKAR_TEST_FLAG", "  ")
    assert env.env_flag("VYSKAR_TEST_FLAG", default) is default
    assert logged(capsys.readouterr().out) == []


def test_an_unknown_flag_word_falls_back_and_is_logged_once(monkeypatch, capsys):
    monkeypatch.setenv("VYSKAR_TEST_FLAG", "disabled")
    assert env.env_flag("VYSKAR_TEST_FLAG", True) is True
    assert env.env_flag("VYSKAR_TEST_FLAG", True) is True
    events = logged(capsys.readouterr().out)
    assert len(events) == 1
    assert events[0]["event"] == "bad_setting"
    assert events[0]["name"] == "VYSKAR_TEST_FLAG"
    assert events[0]["problem"] == "not_on_or_off"
    assert "disabled" not in json.dumps(events[0])  # the value itself is never logged


@pytest.mark.parametrize("raw", ["0", "no", "off", "False ", "FALSE"])
def test_own_keys_turn_off_with_any_off_word(monkeypatch, raw):
    from api.routes import own_keys_allowed

    monkeypatch.setenv("ALLOW_OWN_KEYS", raw)
    assert own_keys_allowed() is False


def test_own_keys_stay_on_by_default(monkeypatch):
    from api.routes import own_keys_allowed

    monkeypatch.delenv("ALLOW_OWN_KEYS", raising=False)
    assert own_keys_allowed() is True


@pytest.mark.parametrize("raw", ["0", "no", "Off"])
def test_screenshots_turn_off_with_any_off_word(monkeypatch, tmp_path, raw):
    from types import SimpleNamespace

    from api.routes import screenshots_dir

    settings = SimpleNamespace(workspaces_dir=tmp_path / "ws")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_SCREENSHOTS", raw)
    assert screenshots_dir(settings) is None
    monkeypatch.delenv("APP_SCREENSHOTS")
    assert screenshots_dir(settings) == tmp_path / "screenshots"
