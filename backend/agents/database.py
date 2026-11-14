"""Graph steps for apps that store data in Supabase.

database:   after the workspace is set up and before the build, because Vite
            bakes VITE_ keys into the bundle at build time. Creates the
            app's database and writes its keys into the workspace.
migrations: after the build and before the tests. Applies the migrations the
            builder wrote.

Keys never go into the graph state, which is traced and kept in memory: the
browser keys go into .env.local for the build, and the migration connection
string into .env.database. Deploys skip every .env file and take the keys
from the Vercel project the database is connected to.

Apps with any other storage pass through both steps unchanged.
"""

from pathlib import Path

from agents.deploy import app_name
from tools import supabase

DATABASE_ENV = ".env.database"

NOT_SET_UP = (
    "This app needs a database, but Vyskar's database setup is missing: "
    "VERCEL_TOKEN and VERCEL_SUPABASE_CONFIG_ID must both be set."
)


LIMIT_REACHED = (
    "This app needs a database, but the free plan's limit of active databases "
    "is reached. Delete or pause an unused Supabase project (at "
    "vercel.com/dashboard/stores or supabase.com/dashboard), then build again."
)


def _provision_error(error: Exception) -> str:
    text = str(error)
    if "project limit" in text or "maximum limits for the number of active free projects" in text:
        return LIMIT_REACHED
    return f"Could not create the app's database: {text}"


def needs_database(state: dict) -> bool:
    return (state.get("architecture") or {}).get("storage") == "supabase"


def _fail(message: str) -> dict:
    # Only database_error: the database step runs in the same graph step as
    # the test planner, and two nodes may not both write "errors" at once.
    return {"database_error": message[:2000]}


def make_database(token: str | None, config_id: str | None, provision=supabase.provision):
    def database(state: dict) -> dict:
        if not needs_database(state):
            return {}
        if not token or not config_id:
            return _fail(NOT_SET_UP)
        name = app_name(state)
        try:
            env = provision(token, name, config_id)
        except Exception as error:
            return _fail(_provision_error(error))
        job_dir = Path(state["workspace_dir"])
        supabase.write_env_file(job_dir, env)
        (job_dir / DATABASE_ENV).write_text(env[supabase.MIGRATION_URL_KEY] + "\n")
        return {"database_name": name}

    return database


def make_migrations(apply=supabase.apply_migrations):
    def migrations(state: dict) -> dict:
        url_file = Path(state["workspace_dir"]) / DATABASE_ENV
        if not needs_database(state) or not url_file.exists():
            return {}
        try:
            applied = apply(url_file.read_text().strip(), Path(state["workspace_dir"]))
        except Exception as error:
            return _fail(f"A database migration failed: {error}")
        return {"migrations_applied": applied}

    return migrations


def after_database(state: dict) -> str:
    return "__end__" if state.get("database_error") else "builder"


def after_migrations(state: dict) -> str:
    # build_done joins the test plan before the tests; a failed migration
    # ends the job instead.
    return "__end__" if state.get("database_error") else "build_done"
