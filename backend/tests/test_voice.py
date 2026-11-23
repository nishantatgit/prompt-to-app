import httpx
import pytest
from fastapi.testclient import TestClient

from api import voice
from tools import sarvam

WAV = b"RIFF" + b"\0" * 40


@pytest.fixture
def client(monkeypatch):
    from api.main import app

    monkeypatch.setenv("SARVAM_API_KEY", "sk_sarvam")
    voice._hits.clear()
    return TestClient(app)


def post(client, body=WAV, content_type="audio/wav"):
    return client.post("/api/transcribe", content=body, headers={"Content-Type": content_type})


def test_voice_is_on_only_with_a_key(client, monkeypatch):
    assert client.get("/api/voice").json() == {"enabled": True}
    monkeypatch.delenv("SARVAM_API_KEY")
    assert client.get("/api/voice").json() == {"enabled": False}
    assert post(client).status_code == 503


def test_a_recording_comes_back_as_english_text(client, monkeypatch):
    sent = {}

    def fake_post(url, **kwargs):
        sent.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={"request_id": "r1", "transcript": " A habit tracker ", "language_code": "hi-IN"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(sarvam.httpx, "post", fake_post)
    response = post(client)
    assert response.json() == {"text": "A habit tracker", "language": "hi-IN"}
    assert sent["url"] == sarvam.API
    assert sent["headers"] == {"api-subscription-key": "sk_sarvam"}
    assert sent["data"]["model"] == "saaras:v4" and sent["data"]["mode"] == "translate"
    assert sent["files"]["file"] == ("speech.wav", WAV, "audio/wav")


def test_unclear_audio_gets_a_friendly_message(client, monkeypatch):
    monkeypatch.setattr(
        sarvam.httpx,
        "post",
        lambda url, **kw: httpx.Response(422, json={}, request=httpx.Request("POST", url)),
    )
    response = post(client)
    assert response.status_code == 422
    assert "Try again" in response.json()["detail"]


def test_a_sarvam_outage_does_not_leak_details(client, monkeypatch):
    monkeypatch.setattr(
        sarvam.httpx,
        "post",
        lambda url, **kw: httpx.Response(500, text="boom", request=httpx.Request("POST", url)),
    )
    response = post(client)
    assert response.status_code == 502
    assert "boom" not in response.text


def test_only_short_wav_recordings_are_accepted(client):
    assert post(client, content_type="audio/webm").status_code == 415
    assert post(client, body=b"").status_code == 400
    assert post(client, body=b"0" * (voice.MAX_BYTES + 1)).status_code == 413


def test_recordings_are_limited_per_network(client, monkeypatch):
    monkeypatch.setattr(voice, "PER_HOUR", 2)
    monkeypatch.setattr(voice, "transcribe", lambda key, audio: ("hi", "en-IN"))
    assert post(client).status_code == 200
    assert post(client).status_code == 200
    assert post(client).status_code == 429


def test_networks_with_no_recent_recording_are_forgotten(client):
    voice._check_limit("5.5.5.5", now=0.0)
    voice._check_limit("6.6.6.6", now=3601.0)
    assert voice._hits.keys() == {"6.6.6.6"}
