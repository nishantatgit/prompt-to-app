"""Whole-number settings read from the environment, without crashing on a typo.

A blank or mistyped value (FREE_TRIAL_BUILDS="" or "five") used to raise
ValueError: at import for module-level settings, which kept the API from
starting, and on every request for the rest, which turned /api/trial,
/api/build and /api/feedback into 500s. Now such a value falls back to the
default and a "bad_setting" event is logged once, with the setting's name,
never its value.
"""

import os
import threading

from api.events import log_event

_reported: set[tuple[str, str]] = set()
_lock = threading.Lock()


def _report(name: str, raw: str, **fields) -> None:
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
        _report(name, raw, problem="not_a_whole_number", using=default)
        return default
    if value < minimum:
        _report(name, raw, problem="below_minimum", minimum=minimum, using=default)
        return default
    return value
