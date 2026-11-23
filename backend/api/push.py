"""Web Push: tell a phone a build finished even when Vyskar is closed.

Off until VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are set (Fly secrets).
VAPID_SUBJECT is optional, a mailto: or https: address push services can
reach about problems; it defaults to https://vyskar.com.

Make a key pair once with:
  uv run python -m api.push

The browser subscribes when it starts a build and sends the subscription
with the job id. When that job finishes, each subscription watching it gets
one push, and the service worker shows it as a notification. Subscriptions
live in SQLite under DATA_DIR, like the build credits.
"""

import base64
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from api.jobs import FINISHED_STATUSES, JOB_FINISHED_HOOKS, get_job
from config import Settings, get_settings
from tools.gate import percent_text

router = APIRouter(prefix="/api")

DEFAULT_SUBJECT = "https://vyskar.com"
# A push that cannot be delivered within an hour is no longer news.
TTL_SECONDS = 3600
# Push services answer these when a subscription has gone (app uninstalled,
# permission withdrawn): it is deleted so it is not tried again.
GONE = {404, 410}
# A build takes minutes, so a watch still there after a day belongs to a job
# that never finished here, such as one cut off by a deploy or restart (jobs
# live in memory). Such watches, and subscriptions not used since, are
# deleted so the database does not keep growing or keep endpoints for good.
STALE_SECONDS = 24 * 3600
# The server posts to the endpoint a browser sends, so only the push services
# of the main browsers are accepted: Chrome and Android, Safari, Firefox, Edge.
PUSH_HOSTS = (
    "fcm.googleapis.com",
    ".push.apple.com",
    ".push.services.mozilla.com",
    ".notify.windows.com",
)

SCHEMA = """
create table if not exists subscriptions (
  endpoint text primary key, p256dh text not null, auth text not null, created real not null
);
create table if not exists watches (
  job_id text not null, endpoint text not null references subscriptions,
  created real not null, primary key (job_id, endpoint)
);
"""


@dataclass(frozen=True)
class PushConfig:
    public_key: str
    private_key: str
    subject: str

    @property
    def enabled(self) -> bool:
        return bool(self.public_key and self.private_key)

    @classmethod
    def from_env(cls) -> "PushConfig":
        return cls(
            public_key=os.getenv("VAPID_PUBLIC_KEY", "").strip(),
            private_key=os.getenv("VAPID_PRIVATE_KEY", "").strip(),
            subject=os.getenv("VAPID_SUBJECT", "").strip() or DEFAULT_SUBJECT,
        )


class PushStore:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def watch(self, job_id: str, endpoint: str, p256dh: str, auth: str) -> None:
        """Save the subscription (or its new keys) and have it watch the job.
        `created` is refreshed each time, so it says when it was last used."""
        now = time.time()
        with self._lock:
            self._forget_stale(now)
            self._db.execute(
                "insert into subscriptions values (?, ?, ?, ?) on conflict(endpoint) do update "
                "set p256dh = excluded.p256dh, auth = excluded.auth, created = excluded.created",
                (endpoint, p256dh, auth, now),
            )
            self._db.execute(
                "insert or ignore into watches values (?, ?, ?)", (job_id, endpoint, now)
            )

    def _forget_stale(self, now: float) -> None:
        """Delete watches older than STALE_SECONDS, then subscriptions that
        watch nothing and were last used before then. Call with the lock held."""
        cutoff = now - STALE_SECONDS
        self._db.execute("delete from watches where created < ?", (cutoff,))
        self._db.execute(
            "delete from subscriptions where created < ? "
            "and endpoint not in (select endpoint from watches)",
            (cutoff,),
        )

    def take_watchers(self, job_id: str) -> list[dict]:
        """The subscriptions watching a job, removing the watches: each job
        is pushed once."""
        with self._lock:
            rows = self._db.execute(
                "select s.endpoint, s.p256dh, s.auth from watches w "
                "join subscriptions s on s.endpoint = w.endpoint where w.job_id = ?",
                (job_id,),
            ).fetchall()
            self._db.execute("delete from watches where job_id = ?", (job_id,))
        return [
            {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
            for endpoint, p256dh, auth in rows
        ]

    def forget(self, endpoint: str) -> None:
        with self._lock:
            self._db.execute("delete from watches where endpoint = ?", (endpoint,))
            self._db.execute("delete from subscriptions where endpoint = ?", (endpoint,))

    def count(self) -> int:
        with self._lock:
            return self._db.execute("select count(*) from subscriptions").fetchone()[0]


_store: PushStore | None = None
_store_lock = threading.Lock()


def push_store(settings: Settings) -> PushStore:
    """One store per process. DATA_DIR is Fly's volume; without it, next to
    the workspaces (fine for tests, lost on deploy)."""
    global _store
    with _store_lock:
        if _store is None:
            folder = os.getenv("DATA_DIR") or settings.workspaces_dir
            _store = PushStore(Path(folder) / "push.db")
        return _store


def build_message(job: dict) -> dict | None:
    """What the notification says, matching the in-page one (notify.js)."""
    status = job.get("status")
    state = job.get("state") or {}
    if status == "succeeded":
        confidence = state.get("confidence")
        body = (
            f"Tests passed: {percent_text(confidence)}%. Tap to open it."
            if confidence is not None
            else "Tap to open it."
        )
        return {
            "title": "Your app is live",
            "body": body,
            "url": state.get("deploy_url") or "/",
            "tag": job["job_id"],
        }
    if status in ("failed", "rejected"):
        return {
            "title": "Your build stopped",
            "body": "Tap to see what happened.",
            "url": "/",
            "tag": job["job_id"],
        }
    return None  # cancelled by the user: they know already


def _send(subscription: dict, payload: str, config: PushConfig) -> None:
    from pywebpush import webpush  # imported here: only needed when push is on

    webpush(
        subscription,
        data=payload,
        vapid_private_key=config.private_key,
        vapid_claims={"sub": config.subject},
        ttl=TTL_SECONDS,
        timeout=10,
    )


def push_job_finished(job: dict, store: PushStore, config: PushConfig, send=_send) -> int:
    """Push a finished job to its watchers. Returns how many were sent."""
    watchers = store.take_watchers(job["job_id"])
    message = build_message(job)
    if not watchers or message is None or not config.enabled:
        return 0
    payload = json.dumps(message)
    sent = 0
    for subscription in watchers:
        try:
            send(subscription, payload, config)
            sent += 1
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in GONE:
                store.forget(subscription["endpoint"])
            # Anything else, such as a push service timing out: a missed
            # notification is not worth more than that.
    return sent


def _on_job_finished(job: dict) -> None:
    config = PushConfig.from_env()
    if not config.enabled:
        return
    push_job_finished(job, push_store(get_settings()), config)


JOB_FINISHED_HOOKS.append(_on_job_finished)


@router.get("/push")
def push_status():
    """Whether the server sends pushes, and the key browsers subscribe with."""
    config = PushConfig.from_env()
    return {"enabled": config.enabled, "public_key": config.public_key if config.enabled else ""}


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class Subscription(BaseModel):
    endpoint: str = Field(pattern=r"^https://", max_length=1000)
    keys: SubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def known_push_service(cls, value: str) -> str:
        if not is_push_service(value):
            raise ValueError("not a known push service")
        return value


def is_push_service(endpoint: str) -> bool:
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.port not in (None, 443):
        return False
    return any(
        host == h.lstrip(".") or (h.startswith(".") and host.endswith(h)) for h in PUSH_HOSTS
    )


class WatchRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    subscription: Subscription


@router.post("/push/subscribe")
def subscribe(req: WatchRequest, settings: Settings = Depends(get_settings)):
    """Push this browser a notification when the job finishes."""
    config = PushConfig.from_env()
    if not config.enabled:
        raise HTTPException(status_code=503, detail="Push notifications aren't on.")
    if get_job(req.job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    sub = req.subscription
    store = push_store(settings)
    store.watch(req.job_id, sub.endpoint, sub.keys.p256dh, sub.keys.auth)
    # The browser subscribes after the person allows notifications, which can
    # take a while. If the build finished in the meantime, its finish hook
    # found no watchers, so the watch would never be pushed or cleared: push
    # it now. take_watchers removes the watch under a lock, so the hook and
    # this call never both send it.
    job = get_job(req.job_id)
    if job and job["status"] in FINISHED_STATUSES:
        push_job_finished(job, store, config, send=_send)
    return {"ok": True}


def generate_keys() -> tuple[str, str]:
    """A new VAPID key pair as base64url strings: (public, private)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private_raw = private.private_numbers().private_value.to_bytes(32, "big")

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return b64(public_raw), b64(private_raw)


if __name__ == "__main__":
    public, private = generate_keys()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
