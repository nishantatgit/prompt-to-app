"""Whole-number and on/off settings read from the environment, without
crashing or quietly misreading a typo.

A blank or mistyped value (FREE_TRIAL_BUILDS="" or "five") used to raise
ValueError: at import for module-level settings, which kept the API from
starting, and on every request for the rest, which turned /api/trial,
/api/build and /api/feedback into 500s. Now such a value falls back to the
default and a "bad_setting" event is logged once, with the setting's name,
never its value. Other settings with their own format (CREDIT_PACKS) report
through report_bad_setting the same way.

On/off settings (ALLOW_OWN_KEYS, ALLOW_SERVER_KEYS, APP_SCREENSHOTS) are read
by env_flag, so they all take the same words: true/false, 1/0, yes/no or
on/off, in any case and with stray spaces. Each used to compare against one
exact spelling, so ALLOW_OWN_KEYS=0, =no or "false " left own keys on, and
ALLOW_SERVER_KEYS=True left server keys off, with nothing in the logs.
"""

import os
import threading

from api.events import log_event

_reported: set[tuple[str, str]] = set()
_lock = threading.Lock()


def report_bad_setting(name: str, raw: str, **fields) -> None:
    # Some settings are read on every request: say it once per bad value.
    with _lock:
        if (name, raw) in _reported:
            return
        _reported.add((name, raw))
    log_event("bad_setting", "", name=name, **fields)


def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        report_bad_setting(name, raw, problem="not_a_whole_number", using=default)
        return default
    if value < minimum:
        report_bad_setting(name, raw, problem="below_minimum", minimum=minimum, using=default)
        return default
    return value


TRUE_WORDS = {"true", "1", "yes", "on"}
FALSE_WORDS = {"false", "0", "no", "off"}


def env_flag(name: str, default: bool) -> bool:
    """An on/off setting. Unset or blank means the default; a word that is
    neither on nor off also means the default, and is logged once."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    word = raw.strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    report_bad_setting(name, raw, problem="not_on_or_off", using=default)
    return default
