import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.keys import KeyRejected
from api import jobs, routes


class Settings(SimpleNamespace):
    def api_key_for(self, provider):
        if not self.server_key:
            raise ValueError("no key")
        return self.server_key


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = Settings(
        workspaces_dir=tmp_path,
        builder_mode="loop",
        graph_recursion_limit=50,
        server_key="sk-ant-vyskar",
    )
    started = []
    monkeypatch.delenv("STUB_LLM", raising=False)
    monkeypatch.delenv("ALLOW_SERVER_KEYS", raising=False)
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "2")
    monkeypatch.setenv("FREE_TRIAL_DAILY_CAP", "50")
    monkeypatch.setattr(routes, "_ledger", None)
    monkeypatch.setattr(routes, "check_key", lambda provider, key: None)
    monkeypatch.setattr(routes, "check_rate_limit", lambda request: None)
    monkeypatch.setattr(routes, "has_capacity", lambda: True)
    monkeypatch.setattr(
        routes, "make_models", lambda provider, key, s, meter=None: started.append((provider, key))
    )
    monkeypatch.setattr(routes, "build_graph", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "submit", lambda *a: None)
    monkeypatch.setattr(routes, "_sweep_trial_databases", lambda ledger: None)
    app.dependency_overrides[routes.get_settings] = lambda: settings
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    test_client = TestClient(app)
    test_client.settings = settings
    test_client.started = started
    yield test_client
    app.dependency_overrides.clear()
    jobs.TRIAL_FINISHED_HOOKS.clear()


def build(client, visitor="visitor-1", **body):
    payload = {"prompt": "A timer", "provider": "openai", **body}
    return client.post("/api/build", json=payload, headers={"X-Vyskar-Visitor": visitor})


def test_a_visitor_without_a_key_gets_free_builds_on_vyskars_key(client):
    assert client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json() == {
        "enabled": True,
        "builds_left": 2,
        "own_keys": True,
        "bonus_available": True,
        "bonus_builds": 2,
    }
    response = build(client)
    assert response.status_code == 202
    # Trial builds always run on Vyskar's Anthropic key, whatever was asked.
    assert client.started == [("anthropic", "sk-ant-vyskar")]
    job = jobs.public_view(jobs.get_job(response.json()["job_id"]))
    assert job["trial"] is True
    assert (
        client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json()["builds_left"]
        == 1
    )


def test_free_builds_run_out(client):
    assert build(client).status_code == 202
    assert build(client).status_code == 202
    response = build(client)
    assert response.status_code == 400
    assert response.json()["detail"] == routes.TRIAL_USED_UP


def test_with_the_trial_off_a_key_is_required(client, monkeypatch):
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "0")
    response = build(client)
    assert response.status_code == 400
    assert response.json()["detail"] == routes.NO_KEY
    status = client.get("/api/trial").json()
    assert (status["enabled"], status["builds_left"]) == (False, 0)


def paused_events(capsys) -> list[dict]:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    return [e for e in map(json.loads, lines) if e["event"] == "builds_paused"]


def test_without_a_server_key_free_builds_pause(client, capsys):
    client.settings.server_key = ""
    response = build(client)
    assert response.status_code == 503
    assert response.json()["detail"] == routes.TRIAL_PAUSED
    [event] = paused_events(capsys)
    assert (event["kind"], event["reason"]) == ("free", "key_missing")


@pytest.mark.parametrize(
    "reason, cause",
    [
        ("no_credit", "Your credit balance is too low to access the Anthropic API."),
        ("rejected", "invalid x-api-key"),
    ],
)
def test_the_log_says_why_free_builds_paused(client, monkeypatch, capsys, reason, cause):
    def refuse(provider, key):
        raise KeyRejected("message for the user", reason=reason) from RuntimeError(cause)

    monkeypatch.setattr(routes, "check_key", refuse)
    response = build(client)
    assert response.status_code == 503
    assert response.json()["detail"] == routes.TRIAL_PAUSED
    [event] = paused_events(capsys)
    assert (event["kind"], event["reason"], event["provider"]) == ("free", reason, "anthropic")
    assert event["detail"] == cause
    assert "sk-ant-vyskar" not in json.dumps(event)  # the key itself is never logged
    assert client.started == []  # no build was started


def test_your_own_key_is_never_counted_as_a_trial(client):
    response = build(client, api_key="sk-own")
    assert response.status_code == 202
    assert client.started == [("openai", "sk-own")]
    assert jobs.public_view(jobs.get_job(response.json()["job_id"]))["trial"] is False
    assert (
        client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json()["builds_left"]
        == 2
    )


def test_a_finished_trial_app_schedules_its_database_for_deletion(client):
    job_id = build(client).json()["job_id"]
    jobs._update(job_id, state={"database_name": "notes-abc123"})
    for hook in jobs.TRIAL_FINISHED_HOOKS:
        hook(jobs.get_job(job_id))
    assert routes._ledger.expired_databases(now=10**12) == ["notes-abc123"]


def test_the_browser_may_send_the_visitor_header_cross_origin(monkeypatch):
    # app.vyskar.com calls api.vyskar.com, so the browser asks first.
    import importlib

    import api.main

    monkeypatch.setenv("CORS_ORIGINS", "https://app.vyskar.com")
    app = importlib.reload(api.main).app
    response = TestClient(app).options(
        "/api/build",
        headers={
            "Origin": "https://app.vyskar.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-vyskar-visitor",
        },
    )
    assert response.status_code == 200


def test_the_admin_page_may_send_its_token_cross_origin(monkeypatch):
    # app.vyskar.com/admin reads api.vyskar.com/api/admin/feedback with a bearer token.
    import importlib

    import api.main

    monkeypatch.setenv("CORS_ORIGINS", "https://app.vyskar.com")
    app = importlib.reload(api.main).app
    response = TestClient(app).options(
        "/api/admin/feedback",
        headers={
            "Origin": "https://app.vyskar.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_a_description_over_the_limit_is_refused_before_any_build(client):
    response = build(client, prompt="x" * (routes.MAX_PROMPT_CHARS + 1))
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "prompt"]
    assert client.started == []
    # Refused requests do not use up a free build.
    left = client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json()
    assert left["builds_left"] == 2


def test_a_blank_description_is_refused(client):
    for blank in ["", "   ", "\n\t "]:
        response = build(client, prompt=blank)
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "string_too_short"
    assert client.started == []


def test_a_description_at_the_limit_builds_and_is_trimmed(client):
    prompt = "  " + "x" * routes.MAX_PROMPT_CHARS + "  "
    response = build(client, prompt=prompt)
    assert response.status_code == 202
    job = jobs.get_job(response.json()["job_id"])
    assert job["prompt"] == "x" * routes.MAX_PROMPT_CHARS
