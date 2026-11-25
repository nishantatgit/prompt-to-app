import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from api.env import env_int

BUILDS_PER_HOUR = env_int("BUILDS_PER_HOUR", 3, minimum=1)
WINDOW_SECONDS = 3600

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    # Fly's proxy sets Fly-Client-IP. request.client is the proxy locally.
    ip = request.headers.get("fly-client-ip")
    if ip:
        return ip
    return request.client.host if request.client else "unknown"


def wait_message(seconds: int) -> str:
    # Rounded up, so the visitor never comes back a minute too early.
    minutes = max(1, math.ceil(seconds / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return f"Too many builds from your network. Try again in {minutes} {unit}."


def _prune(now: float) -> None:
    # Drops networks with no build in the window, so the table does not grow
    # with every address that ever built. Called with the lock held.
    for ip in [ip for ip, hits in _hits.items() if not hits or now - hits[-1] > WINDOW_SECONDS]:
        del _hits[ip]


class HourlyCounter:
    """Counts allowed tries per network over the last hour, for the smaller
    limits (voice, questions, restoring bought builds). Networks with no try
    in the last hour are dropped, so the table does not grow with every
    address that ever came by."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, per_hour: int, now: float | None = None) -> bool:
        """True, and the try is counted, while `key` has fewer than
        `per_hour` tries in the last hour. A refused try is not counted."""
        now = time.monotonic() if now is None else now
        with self._lock:
            idle = [
                k for k, hits in self._hits.items() if not hits or now - hits[-1] > WINDOW_SECONDS
            ]
            for k in idle:
                del self._hits[k]
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= per_hour:
                return False
            hits.append(now)
            return True

    def give_back(self, key: str) -> None:
        """Uncount the latest try for `key`, for a try that failed on our
        side (such as an outage at a provider), so it does not use up the
        network's hour."""
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()

    def keys(self) -> set[str]:
        with self._lock:
            return set(self._hits)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


def check_rate_limit(request: Request) -> None:
    ip = client_ip(request)
    now = time.monotonic()
    with _lock:
        _prune(now)
        hits = _hits[ip]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= BUILDS_PER_HOUR:
            retry_after = max(1, math.ceil(WINDOW_SECONDS - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail=wait_message(retry_after),
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
