"""Vyskar's own AI key failing partway through a free or bought build.

The visitor did not bring that key, so the build must not tell them to add
credit to their own AI account, and a bought build is given back.
"""

import anthropic

from api import jobs, routes
from api.server_key import ServerKeyStatus
from tests.test_credits import buy, client  # noqa: F401
from tests.test_keys import auth_error, no_credit_error


class FailingGraph:
    """Starts, then fails the way a model call does when the key stops working."""

    def __init__(self, error):
        self.error = error

    def stream(self, state, config, stream_mode):
        yield ("updates", {"guard": {"allowed": True}})
        raise self.error


def start_bought_build(client, monkeypatch):  # noqa: F811
    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    response = client.post("/api/build", json={"prompt": "A timer", "provider": "openai"})
    assert response.status_code == 202
    return response.json()["job_id"]


def test_a_bought_build_stopped_by_vyskars_key_is_given_back(client, monkeypatch):  # noqa: F811
    job_id = start_bought_build(client, monkeypatch)
    assert client.get("/api/credits").json()["builds_left"] == 4

    jobs._run(FailingGraph(no_credit_error()), job_id, "A timer", 50)

    view = client.get(f"/api/jobs/{job_id}").json()
    assert view["status"] == "failed"
    assert view["reason"] == jobs.SERVER_KEY_STOPPED
    assert "console.anthropic.com" not in view["reason"]
    assert view["credit_refunded"] is True
    assert client.get("/api/credits").json()["builds_left"] == 5


def test_vyskars_key_failing_midway_pauses_free_builds(client, monkeypatch):  # noqa: F811
    status = ServerKeyStatus(check=lambda provider, key: None)
    monkeypatch.setattr(routes, "server_key_status", status)
    jobs.create_job("free-1", "A timer", trial=True)

    jobs._run(FailingGraph(auth_error(anthropic)), "free-1", "A timer", 50)

    job = jobs.get_job("free-1")
    assert job["reason"] == jobs.SERVER_KEY_STOPPED
    assert job["credit_refunded"] is False  # nothing was bought
    # The next visitor sees free builds as paused instead of starting one.
    assert status.paused_reason("anthropic", "sk-ant-vyskar") == "rejected"


def test_an_own_key_build_still_says_to_fix_the_key(client, monkeypatch):  # noqa: F811
    status = ServerKeyStatus(check=lambda provider, key: None)
    monkeypatch.setattr(routes, "server_key_status", status)
    jobs.create_job("own-1", "A timer")

    jobs._run(FailingGraph(no_credit_error()), "own-1", "A timer", 50)

    reason = jobs.get_job("own-1")["reason"]
    assert reason.startswith("no credit: Your Anthropic account has no credit left.")
    # Someone else's key says nothing about Vyskar's own.
    assert status.paused_reason("anthropic", "sk-ant-vyskar") is None


def test_other_errors_stay_internal_errors(client):  # noqa: F811
    jobs.create_job("free-2", "A timer", trial=True)
    jobs._run(FailingGraph(RuntimeError("disk full")), "free-2", "A timer", 50)
    assert jobs.get_job("free-2")["reason"] == "internal error: disk full"
