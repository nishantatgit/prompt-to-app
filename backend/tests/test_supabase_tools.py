import base64

import httpx
import pytest

from tools import supabase
from tools.vercel import collect_files

KEYS = {
    "VITE_SUPABASE_URL": "https://abc.supabase.co",
    "VITE_SUPABASE_ANON_KEY": "anon",
    "POSTGRES_URL_NON_POOLING": "postgres://u:p@h/db",
    "SUPABASE_SERVICE_ROLE_KEY": "service",
}


class FakeVercel:
    """Answers the Vercel calls the provisioning makes and records them."""

    def __init__(self, project_exists=False, statuses=("available",), keys=KEYS):
        self.calls = []
        self.project_exists = project_exists
        self.statuses = list(statuses)
        self.keys = keys

    def __call__(self, method, url, **kwargs):
        path = url.replace(supabase.API, "")
        self.calls.append((method, path, kwargs.get("json")))
        request = httpx.Request(method, url)

        def reply(status, body):
            return httpx.Response(status, json=body, request=request)

        if method == "POST" and path == "/v11/projects":
            return reply(409, {}) if self.project_exists else reply(200, {"id": "prj_new"})
        if method == "GET" and path.startswith("/v9/projects/"):
            return reply(200, {"id": "prj_old"})
        if path == "/v1/storage/stores/integration/direct":
            return reply(200, {"store": {"id": "store_1", "status": self.statuses.pop(0)}})
        if path == "/storage/stores/store_1":
            return reply(200, {"store": {"id": "store_1", "status": self.statuses.pop(0)}})
        if path.endswith("/connections"):
            return reply(200, {})
        if path.endswith("/env"):
            return reply(200, {"envs": [{"id": f"env_{k}", "key": k} for k in self.keys]})
        if "/env/env_" in path:
            key = path.rsplit("env_", 1)[1]
            return reply(200, {"key": key, "value": self.keys[key]})
        return reply(404, {"error": "unexpected call"})


@pytest.fixture
def vercel(monkeypatch):
    fake = FakeVercel()
    install(monkeypatch, fake)
    return fake


def install(monkeypatch, fake):
    monkeypatch.setattr(supabase.httpx, "post", lambda url, **kw: fake("POST", url, **kw))
    monkeypatch.setattr(supabase.httpx, "get", lambda url, **kw: fake("GET", url, **kw))
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)


def test_provision_creates_connects_and_returns_the_keys(vercel):
    env = supabase.provision("tok", "guestbook-abc123", "icfg_1")

    assert env == KEYS
    create = next(body for m, p, body in vercel.calls if p.endswith("/integration/direct"))
    assert create["integrationConfigurationId"] == "icfg_1"
    assert create["metadata"] == {"region": "bom1", "publicEnvVarPrefix": "VITE_"}
    connect = next(body for m, p, body in vercel.calls if p.endswith("/connections"))
    assert connect == {
        "projectId": "prj_new",
        "envVarEnvironments": ["production", "preview", "development"],
        "makeEnvVarsSensitive": False,
    }


def test_an_existing_project_is_reused(monkeypatch):
    fake = FakeVercel(project_exists=True)
    install(monkeypatch, fake)
    supabase.provision("tok", "guestbook-abc123", "icfg_1")
    connect = next(body for m, p, body in fake.calls if p.endswith("/connections"))
    assert connect["projectId"] == "prj_old"


def test_waits_until_the_database_is_available(monkeypatch):
    fake = FakeVercel(statuses=("initializing", "initializing", "available"))
    install(monkeypatch, fake)
    assert supabase.create_database("tok", "x", "icfg_1") == "store_1"


def test_a_database_in_error_raises(monkeypatch):
    install(monkeypatch, FakeVercel(statuses=("initializing", "error")))
    with pytest.raises(RuntimeError, match="is error"):
        supabase.create_database("tok", "x", "icfg_1")


def test_missing_keys_raise(monkeypatch):
    install(monkeypatch, FakeVercel(keys={"VITE_SUPABASE_URL": "https://abc.supabase.co"}))
    with pytest.raises(RuntimeError, match="VITE_SUPABASE_ANON_KEY"):
        supabase.provision("tok", "x", "icfg_1")


def test_env_file_has_only_the_browser_keys(tmp_path):
    supabase.write_env_file(tmp_path, KEYS)
    text = (tmp_path / ".env.local").read_text()
    assert "VITE_SUPABASE_URL=https://abc.supabase.co" in text
    assert "VITE_SUPABASE_ANON_KEY=anon" in text
    assert "service" not in text and "postgres" not in text


def test_env_files_are_never_deployed(tmp_path):
    (tmp_path / "index.html").write_text("<div></div>")
    (tmp_path / ".env.local").write_text("VITE_SUPABASE_ANON_KEY=anon\n")
    files = [f["file"] for f in collect_files(tmp_path)]
    assert files == ["index.html"]
    assert base64.b64decode(collect_files(tmp_path)[0]["data"]) == b"<div></div>"


class FakeConnection:
    def __init__(self, log, fail_on=None):
        self.log = log
        self.fail_on = fail_on

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.log.append("rollback" if exc[0] else "commit")

    def execute(self, sql):
        if self.fail_on and self.fail_on in sql:
            raise ValueError("syntax error at or near")
        self.log.append(sql)


def migrations(tmp_path, files):
    folder = tmp_path / "supabase" / "migrations"
    folder.mkdir(parents=True)
    for name, sql in files.items():
        (folder / name).write_text(sql)


def test_migrations_run_in_name_order_each_committed(tmp_path):
    migrations(tmp_path, {"002_policies.sql": "create policy", "001_tables.sql": "create table"})
    log = []
    applied = supabase.apply_migrations(
        "postgres://x", tmp_path, connect=lambda url, autocommit: FakeConnection(log)
    )
    assert applied == ["001_tables.sql", "002_policies.sql"]
    assert log == ["create table", "commit", "create policy", "commit"]


def test_a_failing_migration_names_its_file_and_stops(tmp_path):
    migrations(tmp_path, {"001_ok.sql": "create table", "002_bad.sql": "creat policy", "003.sql": "x"})
    log = []
    with pytest.raises(RuntimeError, match="002_bad.sql: syntax error"):
        supabase.apply_migrations(
            "postgres://x",
            tmp_path,
            connect=lambda url, autocommit: FakeConnection(log, fail_on="creat policy"),
        )
    assert log == ["create table", "commit", "rollback"]


def test_no_migrations_folder_applies_nothing(tmp_path):
    assert supabase.apply_migrations("postgres://x", tmp_path) == []


def test_connecting_is_retried_while_the_new_database_starts(tmp_path, monkeypatch):
    import psycopg

    migrations(tmp_path, {"001_tables.sql": "create table"})
    log, attempts = [], []
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)

    def connect(url, autocommit):
        attempts.append(url)
        if len(attempts) < 3:
            raise psycopg.OperationalError("failed to check out a connection")
        return FakeConnection(log)

    assert supabase.apply_migrations("postgres://x", tmp_path, connect=connect) == ["001_tables.sql"]
    assert len(attempts) == 3


def test_connecting_gives_up_after_the_timeout(monkeypatch):
    import psycopg

    clock = iter(range(0, 1000, 30))
    monkeypatch.setattr(supabase.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)

    def connect(url, autocommit):
        raise psycopg.OperationalError("still starting")

    with pytest.raises(psycopg.OperationalError):
        supabase.wait_for_connection("postgres://x", connect, timeout=120)


class DroppingConnection(FakeConnection):
    """The first `drops` executions are cut off, as when Postgres restarts."""

    def __init__(self, log, state):
        super().__init__(log)
        self.state = state

    def execute(self, sql):
        if self.state["drops"] > 0:
            self.state["drops"] -= 1
            import psycopg

            raise psycopg.errors.AdminShutdown("terminating connection due to administrator command")
        self.log.append(sql)


def test_a_migration_cut_off_by_a_restart_is_run_again(tmp_path, monkeypatch):
    migrations(tmp_path, {"001_tables.sql": "create table"})
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)
    log, state = [], {"drops": 2}

    applied = supabase.apply_migrations(
        "postgres://x", tmp_path, connect=lambda url, autocommit: DroppingConnection(log, state)
    )
    assert applied == ["001_tables.sql"]
    assert log == ["rollback", "rollback", "create table", "commit"]


def test_a_connection_that_keeps_dropping_gives_up(tmp_path, monkeypatch):
    migrations(tmp_path, {"001_tables.sql": "create table"})
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)
    state = {"drops": 99}
    with pytest.raises(RuntimeError, match="001_tables.sql: terminating connection"):
        supabase.apply_migrations(
            "postgres://x", tmp_path, connect=lambda url, autocommit: DroppingConnection([], state)
        )
    assert state["drops"] == 99 - supabase.MIGRATION_ATTEMPTS


def test_a_mistake_in_the_sql_is_not_retried(tmp_path, monkeypatch):
    migrations(tmp_path, {"001_bad.sql": "creat table"})
    monkeypatch.setattr(supabase.time, "sleep", lambda s: None)
    attempts = []

    def connect(url, autocommit):
        attempts.append(1)
        return FakeConnection([], fail_on="creat table")

    with pytest.raises(RuntimeError, match="001_bad.sql"):
        supabase.apply_migrations("postgres://x", tmp_path, connect=connect)
    assert len(attempts) == 1
