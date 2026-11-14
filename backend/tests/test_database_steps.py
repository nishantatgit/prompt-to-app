from agents.database import (
    DATABASE_ENV,
    NOT_SET_UP,
    after_database,
    after_migrations,
    make_database,
    make_migrations,
)

KEYS = {
    "VITE_SUPABASE_URL": "https://abc.supabase.co",
    "VITE_SUPABASE_ANON_KEY": "anon",
    "POSTGRES_URL_NON_POOLING": "postgres://u:p@h/db",
    "SUPABASE_SERVICE_ROLE_KEY": "service",
}


def job(tmp_path, storage="supabase"):
    return {
        "job_id": "26-11-13-1794-abcdef1234",
        "workspace_dir": str(tmp_path),
        "requirements": {"app_summary": "A guestbook for visitors"},
        "architecture": {"storage": storage},
    }


def test_apps_without_supabase_pass_through(tmp_path):
    def never(*args):
        raise AssertionError("no database for this app")

    for storage in ("none", "local_storage"):
        state = job(tmp_path, storage)
        assert make_database("tok", "icfg", provision=never)(state) == {}
        assert make_migrations(apply=never)(state) == {}
    assert not (tmp_path / ".env.local").exists()


def test_creates_the_database_and_keeps_keys_out_of_state(tmp_path):
    names = []

    def provision(token, name, config_id):
        names.append((token, name, config_id))
        return KEYS

    out = make_database("tok", "icfg_1", provision=provision)(job(tmp_path))

    assert names == [("tok", "guestbook-visitors-abcdef", "icfg_1")]
    assert out == {"database_name": "guestbook-visitors-abcdef"}
    assert "anon" not in str(out) and "postgres" not in str(out)
    assert "VITE_SUPABASE_ANON_KEY=anon" in (tmp_path / ".env.local").read_text()
    assert (tmp_path / DATABASE_ENV).read_text().strip() == "postgres://u:p@h/db"
    assert after_database(out) == "builder"


def test_missing_setup_ends_the_job_with_a_clear_reason(tmp_path):
    out = make_database(None, "icfg_1")(job(tmp_path))
    assert out["database_error"] == NOT_SET_UP
    assert "errors" not in out  # runs alongside the test planner
    assert after_database(out) == "__end__"


def test_a_failed_provision_ends_the_job(tmp_path):
    def provision(*args):
        raise RuntimeError("Vercel 402: payment required")

    out = make_database("tok", "icfg_1", provision=provision)(job(tmp_path))
    assert out["database_error"].startswith("Could not create the app's database: Vercel 402")
    assert after_database(out) == "__end__"


def test_migrations_use_the_saved_connection_string(tmp_path):
    (tmp_path / DATABASE_ENV).write_text("postgres://u:p@h/db\n")
    seen = []

    def apply(url, job_dir):
        seen.append((url, str(job_dir)))
        return ["001_tables.sql"]

    out = make_migrations(apply=apply)(job(tmp_path))
    assert seen == [("postgres://u:p@h/db", str(tmp_path))]
    assert out == {"migrations_applied": ["001_tables.sql"]}
    assert after_migrations(out) == "build_done"


def test_a_failed_migration_ends_the_job(tmp_path):
    (tmp_path / DATABASE_ENV).write_text("postgres://u:p@h/db\n")

    def apply(url, job_dir):
        raise RuntimeError("002_policies.sql: syntax error")

    out = make_migrations(apply=apply)(job(tmp_path))
    assert out["database_error"] == "A database migration failed: 002_policies.sql: syntax error"
    assert after_migrations(out) == "__end__"


def test_a_database_failure_is_the_jobs_reason():
    from api.jobs import _outcome

    status, reason = _outcome({"database_error": "Could not create the app's database: Vercel 402"})
    assert status == "failed"
    assert reason == "Could not create the app's database: Vercel 402"


def test_the_job_view_names_the_database_but_holds_no_keys():
    from api import jobs

    jobs.create_job("db-1", "a guestbook", "loop")
    jobs._update("db-1", state={"database_name": "guestbook-abc123", "deploy_url": "https://x"})
    view = jobs.public_view(jobs.get_job("db-1"))
    assert view["database_name"] == "guestbook-abc123"
    assert not any("KEY" in k or "POSTGRES" in k for k in view)


def test_the_free_database_limit_gets_a_clear_message(tmp_path):
    from agents.database import LIMIT_REACHED

    def provision(*args):
        raise RuntimeError(
            'Vercel 400: {"error":{"code":"validation_error","message":"The following organization '
            "members have reached their maximum limits for the number of active free projects within "
            'organizations where they are an administrator or owner: nishantatgit (2 project limit)."}}'
        )

    out = make_database("tok", "icfg_1", provision=provision)(job(tmp_path))
    assert out["database_error"] == LIMIT_REACHED
    assert "Vercel 400" not in out["database_error"]


def auth_job(tmp_path):
    state = job(tmp_path)
    state["architecture"]["needs_auth"] = True
    return state


def test_apps_with_logins_turn_off_email_confirmation(tmp_path):
    calls = []
    step = make_database(
        "tok",
        "icfg_1",
        provision=lambda *a: KEYS,
        access_token="sbp_token",
        allow_signups=lambda token, url: calls.append((token, url)),
    )
    out = step(auth_job(tmp_path))
    assert out == {"database_name": "guestbook-visitors-abcdef"}
    assert calls == [("sbp_token", "https://abc.supabase.co")]


def test_apps_without_logins_leave_confirmation_alone(tmp_path):
    def never(*args):
        raise AssertionError("only apps with logins change the auth settings")

    step = make_database("tok", "icfg_1", provision=lambda *a: KEYS, access_token="x", allow_signups=never)
    assert step(job(tmp_path)) == {"database_name": "guestbook-visitors-abcdef"}


def test_logins_without_an_access_token_end_the_job_before_creating_anything(tmp_path):
    from agents.database import NO_ACCESS_TOKEN

    def never(*args):
        raise AssertionError("no database without a way to set up logins")

    out = make_database("tok", "icfg_1", provision=never)(auth_job(tmp_path))
    assert out["database_error"] == NO_ACCESS_TOKEN


def test_a_failed_login_setup_ends_the_job(tmp_path):
    def refuse(token, url):
        raise RuntimeError("Supabase refused the access token (401)")

    step = make_database("tok", "icfg_1", provision=lambda *a: KEYS, access_token="bad", allow_signups=refuse)
    out = step(auth_job(tmp_path))
    assert out["database_error"].startswith("Could not set up logins for the app's database: Supabase refused")
