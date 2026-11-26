"""With VERCEL_TEAM_ID set, every Vercel call of a deploy goes to that team.

A call without teamId lands in the token owner's personal account, so the app
used to deploy there while its edit key, database keys and later changes were
looked up in the team.
"""

import httpx
import pytest

from tools import vercel


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple[str, str, dict]] = []

    def record(method):
        def call(url, **kwargs):
            seen.append((method, url.replace(vercel.API, ""), kwargs.get("params") or {}))
            request = httpx.Request(method, url)
            path = url.replace(vercel.API, "")
            if method == "POST" and path == "/v13/deployments":
                return httpx.Response(200, json={"id": "dpl_1"}, request=request)
            if method == "GET" and path == "/v13/deployments/dpl_1":
                return httpx.Response(200, json={"readyState": "READY"}, request=request)
            return httpx.Response(200, json={}, request=request)

        return call

    monkeypatch.setattr(vercel.httpx, "get", record("GET"))
    monkeypatch.setattr(vercel.httpx, "post", record("POST"))
    return seen


def test_a_deploy_sends_every_call_to_the_team(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("VERCEL_TEAM_ID", "team_abc")
    (tmp_path / "index.html").write_text("<h1>hi</h1>")

    url = vercel.deploy_app("t", tmp_path, "notes")
    vercel.set_project_env("t", "notes", "EDIT_KEY_HASH", "h")

    assert url == "https://notes.vyskar.app"
    paths = [path for _, path, _ in calls]
    assert "/v13/deployments" in paths
    assert "/v13/deployments/dpl_1" in paths
    assert "/v10/projects/vyskar-notes/domains" in paths
    for method, path, params in calls:
        assert params.get("teamId") == "team_abc", f"{method} {path} went to the personal account"


def test_the_deploy_keeps_its_own_parameters_with_the_team(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("VERCEL_TEAM_ID", "team_abc")
    (tmp_path / "index.html").write_text("<h1>hi</h1>")

    vercel.deploy_app("t", tmp_path, "notes")

    create = next(params for method, path, params in calls if path == "/v13/deployments")
    assert create == {"skipAutoDetectionConfirmation": "1", "teamId": "team_abc"}


def test_without_a_team_no_call_names_one(monkeypatch, tmp_path, calls):
    monkeypatch.delenv("VERCEL_TEAM_ID", raising=False)
    (tmp_path / "index.html").write_text("<h1>hi</h1>")

    vercel.deploy_app("t", tmp_path, "notes")

    assert calls
    assert all("teamId" not in params for _, _, params in calls)
