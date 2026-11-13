import anthropic
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from agents import keys
from agents.keys import KeyRejected, check_key, user_error_reason as rejected_reason

REQUEST = httpx.Request("GET", "https://api.example.com/v1/models")


def auth_error(module):
    response = httpx.Response(401, request=REQUEST)
    return module.AuthenticationError("invalid x-api-key", response=response, body=None)


class FakeClient:
    """Stands in for the Anthropic or OpenAI client: models.list() raises
    `error`, messages.create() raises `call_error`, or both return nothing."""

    def __init__(self, error=None, call_error=None):
        self.error = error
        self.call_error = call_error
        self.models = self
        self.messages = self
        self.created = []

    def __call__(self, **kwargs):
        return self

    def list(self, **kwargs):
        if self.error:
            raise self.error

    def create(self, **kwargs):
        self.created.append(kwargs)
        if self.call_error:
            raise self.call_error


def no_credit_error():
    response = httpx.Response(400, request=REQUEST)
    return anthropic.BadRequestError(
        "Your credit balance is too low to access the Anthropic API.", response=response, body=None
    )


def openai_quota_error():
    response = httpx.Response(429, request=REQUEST)
    error = openai.RateLimitError("You exceeded your current quota", response=response, body=None)
    error.code = "insufficient_quota"
    return error


def test_valid_anthropic_key_passes_with_a_one_token_call(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(keys.anthropic, "Anthropic", client)
    check_key("anthropic", "sk-ant-good")
    assert client.created[0]["max_tokens"] == 1


def test_anthropic_account_without_credit_is_caught_before_the_build(monkeypatch):
    monkeypatch.setattr(keys.anthropic, "Anthropic", FakeClient(call_error=no_credit_error()))
    with pytest.raises(KeyRejected, match="Your Anthropic account has no credit left"):
        check_key("anthropic", "sk-ant-broke")


def test_other_errors_from_the_credit_call_do_not_block(monkeypatch):
    response = httpx.Response(404, request=REQUEST)
    missing = anthropic.NotFoundError("model not found", response=response, body=None)
    monkeypatch.setattr(keys.anthropic, "Anthropic", FakeClient(call_error=missing))
    check_key("anthropic", "sk-ant-good")


def test_no_credit_during_a_build_gets_its_own_reason():
    assert rejected_reason(no_credit_error()).startswith("no credit: Your Anthropic account")
    assert rejected_reason(openai_quota_error()).startswith("no credit: Your OpenAI account")


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
