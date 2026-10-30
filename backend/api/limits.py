import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

BUILDS_PER_HOUR = int(os.getenv("BUILDS_PER_HOUR", "3"))
WINDOW_SECONDS = 3600

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    # Fly's proxy sets Fly-Client-IP. request.client is the proxy locally.
    ip = request.headers.get("fly-client-ip")
    if ip:
        return ip
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    ip = client_ip(request)
    now = time.monotonic()
    with _lock:
        hits = _hits[ip]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= BUILDS_PER_HOUR:
            retry_after = int(WINDOW_SECONDS - (now - hits[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Too many builds from your network. Try again in {retry_after // 60 + 1} minutes.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
