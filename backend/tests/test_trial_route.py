from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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
    monkeypatch.setattr(routes, "make_models", lambda provider, key, s: started.append((provider, key)))
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
    }
    response = build(client)
    assert response.status_code == 202
    # Trial builds always run on Vyskar's Anthropic key, whatever was asked.
    assert client.started == [("anthropic", "sk-ant-vyskar")]
    job = jobs.public_view(jobs.get_job(response.json()["job_id"]))
    assert job["trial"] is True
    assert client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json()["builds_left"] == 1


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
    assert client.get("/api/trial").json() == {"enabled": False, "builds_left": 0}


def test_without_a_server_key_free_builds_pause(client):
    client.settings.server_key = ""
    response = build(client)
    assert response.status_code == 503
    assert response.json()["detail"] == routes.TRIAL_PAUSED


def test_your_own_key_is_never_counted_as_a_trial(client):
    response = build(client, api_key="sk-own")
    assert response.status_code == 202
    assert client.started == [("openai", "sk-own")]
    assert jobs.public_view(jobs.get_job(response.json()["job_id"]))["trial"] is False
    assert client.get("/api/trial", headers={"X-Vyskar-Visitor": "visitor-1"}).json()["builds_left"] == 2


def test_a_finished_trial_app_schedules_its_database_for_deletion(client):
    job_id = build(client).json()["job_id"]
    jobs._update(job_id, state={"database_name": "notes-abc123"})
    for hook in jobs.TRIAL_FINISHED_HOOKS:
        hook(jobs.get_job(job_id))
    assert routes._ledger.expired_databases(now=10**12) == ["notes-abc123"]
