import pytest

from agents.database import DATABASE_ENV
from agents.deploy import make_deploy
from agents.qa import test_executor as executor

PASSED = {
    "tests_ok": True,
    "test_summary": "3/3 passed",
    "test_report_path": "r",
    "confidence": 100,
}


@pytest.fixture
def calls(monkeypatch):
    log = []
    monkeypatch.setattr(executor.test_data, "snapshot", lambda url: log.append(("snapshot", url)))
    monkeypatch.setattr(executor.test_data, "restore", lambda url: log.append(("restore", url)))

    def run_tests(state):
        log.append(("tests",))
        return dict(PASSED)

    monkeypatch.setattr(executor, "run_tests", run_tests)
    return log


def with_database(tmp_path, url="postgres://app"):
    (tmp_path / DATABASE_ENV).write_text(url + "\n")
    return {"workspace_dir": str(tmp_path)}


def test_an_app_without_a_database_just_runs_its_tests(tmp_path, calls):
    assert executor.test_executor({"workspace_dir": str(tmp_path)}) == PASSED
    assert calls == [("tests",)]


def test_the_database_is_saved_before_the_tests_and_put_back_after(tmp_path, calls):
    assert executor.test_executor(with_database(tmp_path)) == PASSED
    assert calls == [("snapshot", "postgres://app"), ("tests",), ("restore", "postgres://app")]


def test_the_database_is_put_back_even_when_the_tests_crash(tmp_path, calls, monkeypatch):
    def crash(state):
        raise RuntimeError("playwright crashed")

    monkeypatch.setattr(executor, "run_tests", crash)
    with pytest.raises(RuntimeError, match="playwright crashed"):
        executor.test_executor(with_database(tmp_path))
    assert calls == [("snapshot", "postgres://app"), ("restore", "postgres://app")]


def test_without_a_snapshot_the_tests_do_not_run(tmp_path, calls, monkeypatch):
    def refuse(url):
        raise RuntimeError("permission denied for schema public")

    monkeypatch.setattr(executor.test_data, "snapshot", refuse)
    out = executor.test_executor(with_database(tmp_path))
    assert calls == []  # no tests, so nothing to put back
    assert out["tests_ok"] is False
    assert "couldn't be saved first" in out["test_summary"]
    assert "test_data_error" not in out  # the app still goes online, untested


def test_a_failed_restore_stops_the_deploy(tmp_path, calls, monkeypatch):
    def refuse(url):
        raise RuntimeError("could not put back rows of: ratings")

    monkeypatch.setattr(executor.test_data, "restore", refuse)
    out = executor.test_executor(with_database(tmp_path))
    assert out["tests_ok"] is False
    assert out["test_data_error"].startswith("The tests' data couldn't be removed")
    assert "ratings" in out["test_data_error"]

    deployed = []
    deploy = make_deploy("tok")
    import agents.deploy as deploy_module

    monkeypatch.setattr(deploy_module, "deploy_app", lambda *a: deployed.append(a) or "https://x")
    result = deploy({**out, "workspace_dir": str(tmp_path), "job_id": "j"})
    assert deployed == []
    assert result == {"deploy_url": "", "deploy_error": out["test_data_error"]}
