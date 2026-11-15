from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from agents.deploy import make_deploy
from api import jobs, routes
from tools import edit_key, vercel

KEY = "k" * 43
HASH = edit_key.hash_key(KEY)


def test_a_key_matches_only_its_own_hash():
    key = edit_key.new_key()
    assert len(key) >= 43
    assert edit_key.matches(key, edit_key.hash_key(key))
    assert not edit_key.matches(key, edit_key.hash_key(edit_key.new_key()))
    assert not edit_key.matches(key, None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = SimpleNamespace(
        workspaces_dir=tmp_path, builder_mode="loop", graph_recursion_limit=50
    )
    submitted = []
    stored = {"notes-abc123": HASH, "old-app-111111": None}
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    monkeypatch.setattr(routes, "check_key", lambda provider, key: None)
    monkeypatch.setattr(routes, "check_rate_limit", lambda request: None)
    monkeypatch.setattr(routes, "has_capacity", lambda: True)
    monkeypatch.setattr(routes, "make_models", lambda *a: None)
    monkeypatch.setattr(routes, "build_graph", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "submit", lambda *a: submitted.append(a))
    monkeypatch.setattr(routes, "get_project_env", lambda token, app, key: stored[app])
    # the default argument was bound at import; route the check through the fake
    real = routes.check_edit_key
    monkeypatch.setattr(
        routes, "check_edit_key", lambda app, key: real(app, key, read=routes.get_project_env)
    )
    app.dependency_overrides[routes.get_settings] = lambda: settings
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    c = TestClient(app)
    c.submitted = submitted
    yield c
    app.dependency_overrides.clear()


def build(client, **body):
    payload = {"prompt": "Add a dark mode", "provider": "anthropic", "api_key": "sk-ant-x", **body}
    return client.post("/api/build", json=payload)


def test_a_new_app_gets_an_edit_key_and_only_its_hash_is_kept(client):
    response = build(client, prompt="A notes app")
    key = response.json()["edit_key"]
    extra = client.submitted[0][-1]
    assert extra == {"edit_key_hash": edit_key.hash_key(key)}


def test_the_owner_can_change_their_app(client):
    response = build(client, app="notes-abc123", edit_key=KEY)
    assert response.status_code == 202
    assert response.json()["edit_key"] is None  # the browser already has it
    assert client.submitted[0][-1] == {"app_name": "notes-abc123"}


def test_anyone_else_is_refused_before_any_work(client):
    assert build(client, app="notes-abc123", edit_key="guess").status_code == 403
    assert build(client, app="notes-abc123").status_code == 403
    assert client.submitted == []


def test_apps_without_a_key_cannot_be_changed(client):
    response = build(client, app="old-app-111111", edit_key=KEY)
    assert response.status_code == 404
    assert response.json()["detail"] == routes.NOT_CHANGEABLE


def test_app_names_are_checked(client):
    assert build(client, app="../etc", edit_key=KEY).status_code == 422


def test_without_vercel_changes_are_unavailable(client, monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN")
    assert build(client, app="notes-abc123", edit_key=KEY).status_code == 503


def deploy_state(tmp_path, **kw):
    return {
        "workspace_dir": str(tmp_path),
        "job_id": "j-abc123",
        "requirements": {"app_summary": "Notes"},
        **kw,
    }


def test_a_new_app_saves_its_key_hash_after_deploying(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.deploy.deploy_app", lambda t, d, n: f"https://{n}.vyskar.app")
    saved = []
    deploy = make_deploy("tok", set_env=lambda *a: saved.append(a))
    out = deploy(deploy_state(tmp_path, edit_key_hash=HASH))
    assert out["editable"] is True and out["deployed_name"] == "notes-abc123"
    assert saved == [("tok", "notes-abc123", edit_key.ENV_KEY, HASH)]


def test_a_changed_app_keeps_its_key(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.deploy.deploy_app", lambda t, d, n: f"https://{n}.vyskar.app")
    saved = []
    out = make_deploy("tok", set_env=lambda *a: saved.append(a))(
        deploy_state(tmp_path, app_name="notes-abc123")
    )
    assert saved == [] and out["editable"] is True


def test_a_failed_key_save_still_ships_the_app(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.deploy.deploy_app", lambda t, d, n: "https://x.vyskar.app")

    def fail(*a):
        raise RuntimeError("vercel down")

    out = make_deploy("tok", set_env=fail)(deploy_state(tmp_path, edit_key_hash=HASH))
    assert out["deploy_url"] == "https://x.vyskar.app" and out["editable"] is False


def test_the_job_view_names_the_app():
    jobs.create_job("j-view", "p")
    jobs._update("j-view", state={"deployed_name": "notes-abc123", "editable": True})
    view = jobs.public_view(jobs.get_job("j-view"))
    assert view["app_name"] == "notes-abc123" and view["editable"] is True


def test_project_env_is_read_and_written(monkeypatch):
    calls = []

    def fake(method):
        def call(url, **kw):
            calls.append((method, url.replace(vercel.API, ""), kw.get("json")))
            request = httpx.Request(method, url)
            if url.endswith("/env") and method == "GET":
                return httpx.Response(
                    200, json={"envs": [{"id": "e1", "key": edit_key.ENV_KEY}]}, request=request
                )
            if url.endswith("/env/e1"):
                return httpx.Response(200, json={"value": HASH}, request=request)
            return httpx.Response(201, json={}, request=request)

        return call

    monkeypatch.setattr(vercel.httpx, "get", fake("GET"))
    monkeypatch.setattr(vercel.httpx, "post", fake("POST"))
    assert vercel.get_project_env("t", "notes-abc123", edit_key.ENV_KEY) == HASH
    vercel.set_project_env("t", "notes-abc123", edit_key.ENV_KEY, HASH)
    method, path, body = calls[-1]
    assert (method, path) == ("POST", "/v10/projects/vyskar-notes-abc123/env")
    assert body["type"] == "encrypted" and not body["key"].startswith("VITE_")
