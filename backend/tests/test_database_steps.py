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
    assert out["errors"] == [NOT_SET_UP]
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
