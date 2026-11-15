"""Speech to text with Sarvam, for voice input on phones.

saaras:v4 in translate mode returns English, whatever Indian language or
mix the person spoke (Hindi, Hinglish, Tamil, Indian English and more), so
the agents always get an English request. A request may hold at most 30
seconds of audio.
"""

import httpx

API = "https://api.sarvam.ai/speech-to-text"
MODEL = "saaras:v4"
MAX_SECONDS = 30
# Product words Sarvam should spell as written.
KEYTERMS = '["Vyskar", "app", "dashboard", "login", "to-do"]'


class SpeechError(Exception):
    """The recording could not be turned into text; the message says why."""


def transcribe(key: str, wav: bytes, timeout: float = 30) -> tuple[str, str | None]:
    """English text of a WAV recording, and the language it was spoken in."""
    response = httpx.post(
        API,
        headers={"api-subscription-key": key},
        data={"model": MODEL, "mode": "translate", "keyterms": KEYTERMS},
        files={"file": ("speech.wav", wav, "audio/wav")},
        timeout=timeout,
    )
    if response.status_code == 422:
        raise SpeechError("Couldn't make out that recording. Try again, a little closer.")
    if response.is_error:
        raise RuntimeError(f"Sarvam {response.status_code}: {response.text[:300]}")
    body = response.json()
    return (body.get("transcript") or "").strip(), body.get("language_code")
