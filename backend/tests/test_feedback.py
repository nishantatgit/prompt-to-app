from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.usage import UsageMeter
from api import feedback, jobs, routes
from api.trial import TrialConfig, TrialLedger


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = SimpleNamespace(
        workspaces_dir=tmp_path,
        builder_mode="loop",
        graph_recursion_limit=50,
        api_key_for=lambda provider: "sk-ant-vyskar",
    )
    for name in ("DATA_DIR", "ALLOW_OWN_KEYS", "ALLOW_SERVER_KEYS", "STUB_LLM", "RAZORPAY_KEY_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "2")
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(feedback, "_store", None)
    monkeypatch.setattr(routes, "_ledger", None)
    monkeypatch.setattr(routes, "check_key", lambda provider, key: None)
    monkeypatch.setattr(routes, "check_rate_limit", lambda request: None)
    monkeypatch.setattr(routes, "has_capacity", lambda: True)
    monkeypatch.setattr(routes, "make_models", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "build_graph", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "submit", lambda *a: None)
    monkeypatch.setattr(routes, "_sweep_trial_databases", lambda ledger: None)
    for module in (routes, feedback):
        app.dependency_overrides[module.get_settings] = lambda: settings
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    yield TestClient(app, headers={"X-Vyskar-Visitor": "visitor-1"})
    app.dependency_overrides.clear()
    jobs.TRIAL_FINISHED_HOOKS.clear()


def admin(client):
    return client.get("/api/admin/feedback", headers={"Authorization": "Bearer admin-secret"})


def test_feedback_is_saved_with_the_build_it_is_about(client):
    meter = UsageMeter()
    meter.add("claude-sonnet-5-5", input_tokens=1000, output_tokens=100)
    jobs.create_job("job-fb", "A habit tracker", trial=True, meter=meter)
    jobs._update(
        "job-fb",
        status="failed",
        reason="build failed",
        state={"deployed_name": "habit-ab12cd", "confidence": 40},
    )
    response = client.post(
        "/api/feedback",
        json={"job_id": "job-fb", "rating": "down", "message": "Streaks never saved"},
    )
    assert response.status_code == 200
    row = admin(client).json()["feedback"][0]
    assert (row["kind"], row["rating"], row["message"]) == (
        "feedback",
        "down",
        "Streaks never saved",
    )
    assert row["build"]["prompt"] == "A habit tracker"
    assert row["build"]["status"] == "failed" and row["build"]["app"] == "habit-ab12cd"
    assert row["build"]["cost_usd"] > 0


def test_real_feedback_earns_more_free_builds_once(client):
    message = "The app looked great but the delete button did nothing for me."
    first = client.post("/api/feedback", json={"message": message}).json()
    assert first == {"ok": True, "bonus_builds": 2}
    assert client.get("/api/trial").json()["builds_left"] == 4
    assert client.get("/api/trial").json()["bonus_available"] is False
    again = client.post("/api/feedback", json={"message": message}).json()
    assert again["bonus_builds"] == 0
    assert client.get("/api/trial").json()["builds_left"] == 4


def test_no_bonus_is_offered_when_it_is_set_to_zero(client, monkeypatch):
    monkeypatch.setenv("FREE_TRIAL_BUILDS", "1")
    monkeypatch.setenv("FEEDBACK_BONUS_BUILDS", "0")
    trial = client.get("/api/trial").json()
    # Otherwise the used-up screen says "get 0 more builds".
    assert trial["bonus_available"] is False
    assert trial["builds_left"] == 1
    message = "The app looked great but the delete button did nothing for me."
    assert client.post("/api/feedback", json={"message": message}).json()["bonus_builds"] == 0
    assert client.get("/api/trial").json()["builds_left"] == 1


def test_a_mistyped_bonus_setting_is_not_a_500_after_saving(client, monkeypatch):
    # It used to fail after the feedback was stored, so a retry saved it twice.
    monkeypatch.setenv("FEEDBACK_BONUS_BUILDS", "two")
    assert client.get("/api/trial").status_code == 200
    message = "The app looked great but the delete button did nothing for me."
    response = client.post("/api/feedback", json={"message": message})
    assert response.status_code == 200
    assert response.json()["bonus_builds"] == 2
    assert len(admin(client).json()["feedback"]) == 1


def test_a_thumbs_up_alone_earns_nothing(client):
    assert client.post("/api/feedback", json={"rating": "up"}).json()["bonus_builds"] == 0
    assert client.post("/api/feedback", json={"message": "ok"}).json()["bonus_builds"] == 0


def test_empty_feedback_and_bad_emails_are_refused(client):
    assert client.post("/api/feedback", json={}).status_code == 400
    assert client.post("/api/feedback", json={"rating": "up", "email": "nope"}).status_code == 400


def test_feedback_is_limited_per_day(client, monkeypatch):
    monkeypatch.setattr(feedback, "PER_DAY", 2)
    assert client.post("/api/feedback", json={"rating": "up"}).status_code == 200
    assert client.post("/api/feedback", json={"rating": "up"}).status_code == 200
    assert client.post("/api/feedback", json={"rating": "up"}).status_code == 429


def test_people_without_a_visitor_id_are_limited_by_their_own_network(client, monkeypatch):
    monkeypatch.setattr(feedback, "PER_DAY", 2)
    for ip in ("203.0.113.1", "203.0.113.2"):
        assert (
            client.post(
                "/api/waitlist",
                json={"email": "asha@example.com"},
                headers={"X-Vyskar-Visitor": "", "Fly-Client-IP": ip},
            ).status_code
            == 200
        )
    # Two people on other networks used the empty id: a third is still let in.
    fresh = {"X-Vyskar-Visitor": "", "Fly-Client-IP": "203.0.113.3"}
    for _ in range(2):
        assert client.post("/api/feedback", json={"rating": "up"}, headers=fresh).status_code == 200
    # Their own network's limit still applies.
    assert client.post("/api/feedback", json={"rating": "up"}, headers=fresh).status_code == 429


def test_the_waitlist_keeps_emails(client):
    assert client.post("/api/waitlist", json={"email": "asha@example.com"}).status_code == 200
    assert client.post("/api/waitlist", json={"email": "not an email"}).status_code == 400
    row = admin(client).json()["feedback"][0]
    assert (row["kind"], row["email"]) == ("waitlist", "asha@example.com")


def test_only_the_admin_reads_feedback(client, monkeypatch):
    assert client.get("/api/admin/feedback").status_code == 401
    assert (
        client.get("/api/admin/feedback", headers={"Authorization": "Bearer guess"}).status_code
        == 401
    )
    monkeypatch.delenv("ADMIN_TOKEN")
    assert (
        client.get("/api/admin/feedback", headers={"Authorization": "Bearer "}).status_code == 401
    )


def test_a_non_ascii_token_is_refused_not_a_crash(client):
    # Starlette reads header bytes as latin-1, so this arrives as "Bearer café".
    headers = {"Authorization": "Bearer café".encode("latin-1")}
    assert client.get("/api/admin/feedback", headers=headers).status_code == 401


def test_own_keys_can_be_switched_off(client, monkeypatch):
    payload = {"prompt": "A timer", "provider": "anthropic", "api_key": "sk-own"}
    assert client.post("/api/build", json=payload).status_code == 202
    monkeypatch.setenv("ALLOW_OWN_KEYS", "false")
    response = client.post("/api/build", json=payload)
    assert response.status_code == 400 and response.json()["detail"] == routes.OWN_KEYS_OFF
    assert client.get("/api/trial").json()["own_keys"] is False
    # Free builds still work without a key.
    del payload["api_key"]
    assert client.post("/api/build", json=payload).status_code == 202


def test_free_build_counts_live_on_the_volume(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "volume"))
    client.post("/api/build", json={"prompt": "A timer", "provider": "anthropic"})
    reloaded = TrialLedger(tmp_path / "volume" / "trial-usage.json")
    assert reloaded.builds_left(TrialConfig(2, 50), "visitor-1", "testclient") == 1
