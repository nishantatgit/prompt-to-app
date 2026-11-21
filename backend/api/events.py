"""Build lifecycle events as one JSON object per line on stdout.

Fly collects stdout, so each line can be filtered by its "event" field, for
example: fly logs -a <app> | grep '"event": "build_finish"'

Events: build_start, build_stage, build_finish, build_cost. Every line has
"event", "ts" (unix seconds) and "job_id".

builds_paused is logged when a free or bought build is refused because
Vyskar's own key can't be used; it has no job yet, so its job_id is empty,
and "reason" says why: key_missing, rejected or no_credit. Prompts and user keys are never
logged, only their sizes and flags.

bad_setting is logged once when a whole-number setting such as
FREE_TRIAL_BUILDS is blank or mistyped; "name" says which, "using" is the
default used instead, and the value itself is never logged (see api/env.py).
"""

import json
import sys
import time


def log_event(event: str, job_id: str, **fields) -> None:
    record = {"event": event, "ts": round(time.time(), 3), "job_id": job_id, **fields}
    try:
        line = json.dumps(record, default=str)
    except (TypeError, ValueError):
        # A field that can't be written must never break a build.
        line = json.dumps({"event": event, "ts": record["ts"], "job_id": job_id})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
