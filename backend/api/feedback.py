"""Feedback from people trying Vyskar, kept with the build it is about.

- POST /api/feedback: a rating and/or a message, optionally about one build.
  The build's prompt, status, app and cost are saved with it, so a complaint
  can be traced to the exact build. A real message, from someone on free
  builds, earns FEEDBACK_BONUS_BUILDS more, once.
- POST /api/waitlist: an email, from someone who wants paid builds.
- GET /api/admin/feedback: everything, newest first, with ADMIN_TOKEN.

Stored in SQLite on Fly's volume (DATA_DIR).
"""

import hmac
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from api.jobs import get_job
from api.limits import client_ip
from api.trial import TrialConfig
from config import Settings, get_settings

router = APIRouter(prefix="/api")

MIN_MESSAGE_FOR_BONUS = 20
PER_DAY = 20
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
create table if not exists feedback (
  id integer primary key autoincrement, created real not null, kind text not null,
  visitor text, ip text, job_id text, rating text, message text, email text,
  build text
);
create index if not exists feedback_visitor on feedback (visitor, created);
"""


class FeedbackStore:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def add(self, kind: str, **fields) -> None:
        columns = ("visitor", "ip", "job_id", "rating", "message", "email", "build")
        values = [fields.get(c) for c in columns]
        with self._lock:
            self._db.execute(
                f"insert into feedback (created, kind, {', '.join(columns)}) "
                f"values (?, ?, {', '.join('?' * len(columns))})",
                (time.time(), kind, *values),
            )

    def count_today(self, visitor: str, ip: str) -> int:
        """Entries in the last day from this visitor or this IP. Without a
        visitor id (storage blocked) only the IP counts: matching the empty
        id would put everyone without one under a single shared limit."""
        since = time.time() - 86400
        with self._lock:
            if not visitor:
                return self._db.execute(
                    "select count(*) from feedback where created > ? and ip = ?", (since, ip)
                ).fetchone()[0]
            return self._db.execute(
                "select count(*) from feedback where created > ? and (visitor = ? or ip = ?)",
                (since, visitor, ip),
            ).fetchone()[0]

    def all(self, limit: int = 500) -> list[dict]:
        with self._lock:
            cursor = self._db.execute(
                "select * from feedback order by created desc limit ?", (limit,)
            )
            names = [d[0] for d in cursor.description]
            rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        for row in rows:
            row["build"] = json.loads(row["build"]) if row["build"] else None
        return rows


_store: FeedbackStore | None = None


def feedback_store(settings: Settings) -> FeedbackStore:
    global _store
    if _store is None:
        folder = os.getenv("DATA_DIR") or settings.workspaces_dir
        _store = FeedbackStore(Path(folder) / "feedback.db")
    return _store


def _visitor(request: Request) -> str:
    return request.headers.get("x-vyskar-visitor", "").strip()[:64]


def _build_snapshot(job_id: str | None) -> str | None:
    """What the build was, so the feedback makes sense later."""
    job = get_job(job_id) if job_id else None
    if job is None:
        return None
    state = job.get("state") or {}
    usage = job["meter"].summary() if job.get("meter") else None
    return json.dumps(
        {
            "prompt": job.get("prompt"),
            "status": job.get("status"),
            "reason": job.get("reason"),
            "trial": job.get("trial"),
            "app": state.get("deployed_name") or state.get("app_name"),
            "deploy_url": state.get("deploy_url"),
            "confidence": state.get("confidence"),
            "test_summary": state.get("test_summary"),
            "cost_usd": usage and usage["cost_usd"],
        }
    )


def _check_limit(store: FeedbackStore, visitor: str, ip: str) -> None:
    if store.count_today(visitor, ip) >= PER_DAY:
        raise HTTPException(status_code=429, detail="Thanks! That's plenty of feedback for today.")


class FeedbackRequest(BaseModel):
    job_id: str | None = Field(default=None, max_length=64)
    rating: Literal["up", "down"] | None = None
    message: str = Field(default="", max_length=4000)
    email: str | None = Field(default=None, max_length=200)


@router.post("/feedback")
def send_feedback(
    req: FeedbackRequest, request: Request, settings: Settings = Depends(get_settings)
):
    message = req.message.strip()
    if not message and not req.rating:
        raise HTTPException(status_code=400, detail="Write a few words or pick a rating.")
    email = (req.email or "").strip() or None
    if email and not EMAIL.match(email):
        raise HTTPException(status_code=400, detail="That email doesn't look right.")
    store = feedback_store(settings)
    visitor, ip = _visitor(request), client_ip(request)
    _check_limit(store, visitor, ip)
    store.add(
        "feedback",
        visitor=visitor,
        ip=ip,
        job_id=req.job_id,
        rating=req.rating,
        message=message,
        email=email,
        build=_build_snapshot(req.job_id),
    )
    bonus = 0
    config = TrialConfig.from_env()
    if config.enabled and len(message) >= MIN_MESSAGE_FOR_BONUS:
        # Imported here: routes imports this module's router.
        from api.routes import trial_ledger

        builds = int(os.getenv("FEEDBACK_BONUS_BUILDS", "2"))
        if trial_ledger(settings).grant_bonus(visitor, builds):
            bonus = builds
    return {"ok": True, "bonus_builds": bonus}


class WaitlistRequest(BaseModel):
    email: str = Field(max_length=200)


@router.post("/waitlist")
def join_waitlist(
    req: WaitlistRequest, request: Request, settings: Settings = Depends(get_settings)
):
    email = req.email.strip()
    if not EMAIL.match(email):
        raise HTTPException(status_code=400, detail="That email doesn't look right.")
    store = feedback_store(settings)
    visitor, ip = _visitor(request), client_ip(request)
    _check_limit(store, visitor, ip)
    store.add("waitlist", visitor=visitor, ip=ip, email=email)
    return {"ok": True}


@router.get("/admin/feedback")
def read_feedback(
    authorization: str = Header(default=""), settings: Settings = Depends(get_settings)
):
    token = os.getenv("ADMIN_TOKEN", "")
    given = authorization.removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(given, token):
        raise HTTPException(status_code=401, detail="Not allowed.")
    return {"feedback": feedback_store(settings).all()}
