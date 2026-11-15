"""Voice input for phones: the browser records, Sarvam turns it into text."""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from api.limits import client_ip
from tools.sarvam import SpeechError, transcribe

router = APIRouter(prefix="/api")

# 30 seconds of 16 kHz, 16-bit mono WAV is about 0.96 MB.
MAX_BYTES = 1_100_000
PER_HOUR = int(os.getenv("VOICE_PER_HOUR", "40"))
NOT_SET_UP = "Voice is not set up on this server."

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _check_limit(ip: str, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _lock:
        hits = _hits[ip]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= PER_HOUR:
            raise HTTPException(status_code=429, detail="Too many recordings. Type for now.")
        hits.append(now)


@router.get("/voice")
def voice_status():
    """Whether the server can turn speech into text."""
    return {"enabled": bool(os.environ.get("SARVAM_API_KEY"))}


@router.post("/transcribe")
async def transcribe_speech(request: Request):
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail=NOT_SET_UP)
    if not request.headers.get("content-type", "").startswith("audio/wav"):
        raise HTTPException(status_code=415, detail="Send the recording as audio/wav.")
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="The recording was empty.")
    if len(audio) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Recordings can be up to 30 seconds.")
    _check_limit(client_ip(request))
    try:
        text, language = transcribe(key, audio)
    except SpeechError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except Exception:
        raise HTTPException(
            status_code=502, detail="Voice isn't working right now. Type your app instead."
        ) from None
    if not text:
        raise HTTPException(status_code=422, detail="Didn't hear any words. Try again.")
    return {"text": text, "language": language}
