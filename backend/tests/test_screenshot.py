import os
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.graph import AgentLimits, AgentModels, build_graph
from agents.screenshot import make_screenshot
from agents.stub_llm import StubLLM
from api import jobs, routes
from api.main import app
from tools import screenshot as shot_tools
from tools.screenshot import KEEP_SECONDS, remove_old, take_screenshot

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def state(tmp_path, **extra):
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    return {
        "job_id": "job-1",
        "workspace_dir": str(workspace),
        "deploy_url": "https://notes-abc123.vyskar.app",
        **extra,
    }


def fake_take(calls, ok=True):
    def take(workspace, url, out):
        calls.append((workspace, url, out))
        if ok:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(JPEG)
        return ok

    return take


def test_after_deploy_a_photo_of_the_live_app_is_saved(tmp_path):
    calls = []
    folder = tmp_path / "shots"
    out = make_screenshot(folder, take=fake_take(calls))(state(tmp_path))
    assert out == {"screenshot_path": str(folder / "job-1.jpg")}
    workspace, url, path = calls[0]
    assert workspace == tmp_path / "ws" and url == "https://notes-abc123.vyskar.app"
    assert path.read_bytes() == JPEG


@pytest.mark.parametrize("missing", ["deploy_url", "workspace_dir"])
def test_no_photo_without_a_live_app(tmp_path, missing):
    calls = []
    s = state(tmp_path)
    s[missing] = ""
    assert make_screenshot(tmp_path, take=fake_take(calls))(s) == {}
    assert calls == []


def test_no_folder_turns_photos_off(tmp_path):
    calls = []
    assert make_screenshot(None, take=fake_take(calls))(state(tmp_path)) == {}
    assert calls == []


def test_a_failed_photo_never_fails_the_build(tmp_path):
    def boom(*a):
        raise RuntimeError("chromium crashed")

    assert make_screenshot(tmp_path, take=boom)(state(tmp_path)) == {}
    assert make_screenshot(tmp_path, take=fake_take([], ok=False))(state(tmp_path)) == {}


def test_the_photo_is_taken_after_deploy_and_ends_the_graph(tmp_path):
    models = AgentModels(
        **{
            a: StubLLM(agent=a)
            for a in ["guard", "analyst", "architect", "test_planner", "builder", "validator"]
        }
    )
    graph = build_graph(models, AgentLimits(2, 2, 2, 3, 2), tmp_path)
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("deploy", "screenshot") in edges
    assert ("screenshot", "__end__") in edges
    assert ("deploy", "__end__") not in edges
    assert jobs.STAGES["screenshot"] == "deploying"


def test_take_screenshot_runs_the_node_script_in_the_workspace(tmp_path, monkeypatch):
    seen = {}
    out = tmp_path / "shots" / "job-1.jpg"

    def run(cwd, args, timeout=300, env=None):
        seen.update(cwd=cwd, args=args, timeout=timeout)
        out.write_bytes(JPEG)
        return SimpleNamespace(ok=True, log="")

    monkeypatch.setattr(shot_tools, "run_command", run)
    assert take_screenshot(tmp_path, "https://x.vyskar.app", out) is True
    assert seen["cwd"] == tmp_path
    assert seen["args"] == ["node", str(shot_tools.SCRIPT), "https://x.vyskar.app", str(out)]
    assert shot_tools.SCRIPT.is_file()


def test_take_screenshot_reports_a_failed_run(tmp_path, monkeypatch):
    out = tmp_path / "job-1.jpg"
    out.write_bytes(JPEG)  # an old photo must not pass for a new one
    monkeypatch.setattr(
        shot_tools, "run_command", lambda *a, **k: SimpleNamespace(ok=False, log="timed out")
    )
    assert take_screenshot(tmp_path, "https://x.vyskar.app", out) is False
    assert not out.exists()


def test_old_photos_are_removed(tmp_path):
    old, new = tmp_path / "old.jpg", tmp_path / "new.jpg"
    old.write_bytes(JPEG)
    new.write_bytes(JPEG)
    now = time.time()
    os.utime(old, (now - KEEP_SECONDS - 60,) * 2)
    remove_old(tmp_path, now=now)
    assert not old.exists() and new.exists()
    remove_old(tmp_path / "missing", now=now)  # no folder yet is fine


def finished_job(tmp_path, job_id, status="succeeded", photo=True):
    path = tmp_path / f"{job_id}.jpg"
    if photo:
        path.write_bytes(JPEG)
    jobs.create_job(job_id, "p")
    jobs._update(job_id, status=status, state={"screenshot_path": str(path)})
    return path


def test_the_job_view_links_the_photo_only_once_the_build_succeeded(tmp_path):
    finished_job(tmp_path, "s-ok")
    finished_job(tmp_path, "s-running", status="running")
    finished_job(tmp_path, "s-gone", photo=False)
    view = lambda job_id: jobs.public_view(jobs.get_job(job_id))["screenshot_url"]  # noqa: E731
    assert view("s-ok") == "/api/jobs/s-ok/screenshot"
    assert view("s-running") == ""
    assert view("s-gone") == ""


def test_the_photo_is_served_as_a_jpeg(tmp_path):
    finished_job(tmp_path, "s-serve")
    finished_job(tmp_path, "s-busy", status="running")
    client = TestClient(app)
    response = client.get("/api/jobs/s-serve/screenshot")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == JPEG
    assert client.get("/api/jobs/s-busy/screenshot").status_code == 404
    assert client.get("/api/jobs/nope/screenshot").status_code == 404


def test_photos_go_to_the_data_volume_and_can_be_switched_off(tmp_path, monkeypatch):
    settings = SimpleNamespace(workspaces_dir=tmp_path / "ws")
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("APP_SCREENSHOTS", raising=False)
    assert routes.screenshots_dir(settings) == tmp_path / "ws" / "screenshots"
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    assert routes.screenshots_dir(settings) == tmp_path / "data" / "screenshots"
    monkeypatch.setenv("APP_SCREENSHOTS", "false")
    assert routes.screenshots_dir(settings) is None
