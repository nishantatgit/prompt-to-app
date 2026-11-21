"""Whether Vyskar's own AI key works, so the app can say free builds are
paused before someone taps Build, instead of offering a build the server is
about to refuse.

The key is checked with check_key (one token on the cheapest model) at most
once every CHECK_SECONDS, and every build that runs on Vyskar's key reports
what it found, so a fixed or broken key shows within minutes.
"""

import threading
import time

from agents.keys import KeyRejected, check_key

CHECK_SECONDS = 600


class ServerKeyStatus:
    def __init__(self, check=check_key, clock=time.time):
        self._check = check
        self._clock = clock
        self._lock = threading.Lock()
        self._checked_at: float | None = None
        self._reason: str | None = None

    def record(self, reason: str | None) -> None:
        """What a check or a build found: None when the key worked, else
        key_missing, rejected or no_credit."""
        with self._lock:
            self._reason = reason
            self._checked_at = self._clock()

    def paused_reason(self, provider: str, key: str | None) -> str | None:
        """Why builds on Vyskar's key are paused, or None when they are not.
        Checks the key again once the last answer is older than CHECK_SECONDS."""
        if not key:
            self.record("key_missing")
            return "key_missing"
        with self._lock:
            fresh = (
                self._checked_at is not None and self._clock() - self._checked_at < CHECK_SECONDS
            )
            if fresh:
                return self._reason
        # Outside the lock: the check is a network call, and two at once is fine.
        try:
            self._check(provider, key)
            reason = None
        except KeyRejected as error:
            reason = error.reason
        self.record(reason)
        return reason


server_key_status = ServerKeyStatus()
