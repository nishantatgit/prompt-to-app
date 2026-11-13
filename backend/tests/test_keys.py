import anthropic
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from agents import keys
from agents.keys import KeyRejected, check_key, rejected_reason

REQUEST = httpx.Request("GET", "https://api.example.com/v1/models")


def auth_error(module):
    response = httpx.Response(401, request=REQUEST)
    return module.AuthenticationError("invalid x-api-key", response=response, body=None)


class FakeClient:
    """Stands in for the Anthropic or OpenAI client: models.list() raises
    the given error, or returns nothing when there is none."""

    def __init__(self, error=None):
        self.error = error
        self.models = self

    def __call__(self, **kwargs):
        return self

    def list(self, **kwargs):
        if self.error:
            raise self.error


def test_valid_anthropic_key_passes(monkeypatch):
    monkeypatch.setattr(keys.anthropic, "Anthropic", FakeClient())
    check_key("anthropic", "sk-ant-good")


def test_rejected_anthropic_key_raises_a_clear_message(monkeypatch):
    monkeypatch.setattr(keys.anthropic, "Anthropic", FakeClient(auth_error(anthropic)))
    with pytest.raises(KeyRejected, match="Your Anthropic key was rejected"):
        check_key("anthropic", "sk-ant-bad")


def test_rejected_openai_key_raises_a_clear_message(monkeypatch):
    monkeypatch.setattr(keys.openai, "OpenAI", FakeClient(auth_error(openai)))
    with pytest.raises(KeyRejected, match="Your OpenAI key was rejected"):
        check_key("openai", "sk-bad")


def test_provider_outage_does_not_block_the_build(monkeypatch):
    outage = anthropic.APIConnectionError(request=REQUEST)
    monkeypatch.setattr(keys.anthropic, "Anthropic", FakeClient(outage))
    check_key("anthropic", "sk-ant-good")


def test_key_rejected_during_a_build_gets_its_own_reason():
    assert rejected_reason(auth_error(anthropic)).startswith("key rejected: Your Anthropic key")
    assert rejected_reason(auth_error(openai)).startswith("key rejected: Your OpenAI key")
    assert rejected_reason(ValueError("boom")) is None


def test_build_with_a_rejected_key_returns_400_before_starting(monkeypatch):
    from api import routes
    from api.main import app

    def reject(provider, key):
        raise KeyRejected(keys.rejected_message(provider))

    monkeypatch.delenv("STUB_LLM", raising=False)
    monkeypatch.setattr(routes, "check_key", reject)
    # The key check runs before settings are used, so empty ones will do.
    app.dependency_overrides[routes.get_settings] = lambda: None
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    try:
        response = TestClient(app).post(
            "/api/build",
            json={"prompt": "a timer", "provider": "anthropic", "api_key": "sk-ant-bad"},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Your Anthropic key was rejected")
