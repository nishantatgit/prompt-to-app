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
