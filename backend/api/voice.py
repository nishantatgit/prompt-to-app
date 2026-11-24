"""Voice input for phones: the browser records, Sarvam turns it into text."""

import os

from fastapi import APIRouter, HTTPException, Request

from api.env import env_int
from api.limits import HourlyCounter, client_ip
from tools.sarvam import SpeechError, transcribe

router = APIRouter(prefix="/api")

# 30 seconds of 16 kHz, 16-bit mono WAV is about 0.96 MB.
MAX_BYTES = 1_100_000
PER_HOUR = env_int("VOICE_PER_HOUR", 40, minimum=1)
NOT_SET_UP = "Voice is not set up on this server."
TOO_LONG = "Recordings can be up to 30 seconds."

_hits = HourlyCounter()


def _check_limit(ip: str, now: float | None = None) -> None:
    if not _hits.allow(ip, PER_HOUR, now):
        raise HTTPException(status_code=429, detail="Too many recordings. Type for now.")


async def _read_capped(request: Request) -> bytes:
    """The request body, refused as soon as it is longer than MAX_BYTES.

    Reading it all first would let one upload of any size sit in the API's
    memory before the length check, so the declared length is checked up
    front and the body is read in chunks that stop past the cap.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=TOO_LONG)
    audio = bytearray()
    async for chunk in request.stream():
        audio += chunk
        if len(audio) > MAX_BYTES:
            raise HTTPException(status_code=413, detail=TOO_LONG)
    return bytes(audio)


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
    audio = await _read_capped(request)
    if not audio:
        raise HTTPException(status_code=400, detail="The recording was empty.")
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
