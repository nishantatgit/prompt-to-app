"""A Supabase database for each app, created through the Vercel Marketplace.

Order of calls, all with the deploy token:
1. create the Vercel project the app will later deploy to
2. create a Supabase database through the installed Supabase integration
3. connect the database to the project, which puts its keys on the project
   as environment variables for production, preview and development
4. read the keys back, one variable at a time (the list call only returns
   encrypted values)

The keys go into the job's workspace so the local build and tests can use
the database. Deploys get them from the project itself.
"""

import time
from pathlib import Path

import httpx
import psycopg

from tools.vercel import API, _check, _headers, _params

# Mumbai: close to Vyskar's users and to Vercel's bom1 functions.
REGION = "bom1"
ENVIRONMENTS = ["production", "preview", "development"]

# Keys the browser may see. Vite only exposes variables with this prefix.
PUBLIC_KEYS = ("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY")
# The connection string used to apply migrations, bypassing the pooler.
MIGRATION_URL_KEY = "POSTGRES_URL_NON_POOLING"


def create_project(token: str, name: str) -> str:
    """The project's id, creating it when it does not exist yet."""
    response = httpx.post(
        f"{API}/v11/projects",
        params=_params(),
        headers=_headers(token),
        json={"name": name, "framework": "vite"},
        timeout=30,
    )
    if response.status_code == 409:
        response = httpx.get(
            f"{API}/v9/projects/{name}", params=_params(), headers=_headers(token), timeout=30
        )
    _check(response)
    return response.json()["id"]


def create_database(token: str, name: str, config_id: str, timeout: int = 120) -> str:
    """Create a free Supabase database and wait until it is available."""
    response = httpx.post(
        f"{API}/v1/storage/stores/integration/direct",
        params=_params(),
        headers=_headers(token),
        json={
            "name": name,
            "integrationConfigurationId": config_id,
            "integrationProductIdOrSlug": "supabase",
            "metadata": {"region": REGION, "publicEnvVarPrefix": "VITE_"},
        },
        timeout=120,
    )
    _check(response)
    store = response.json()["store"]
    deadline = time.monotonic() + timeout
    while store.get("status") != "available":
        if store.get("status") == "error" or time.monotonic() > deadline:
            raise RuntimeError(f"Supabase database {name} is {store.get('status')}")
        time.sleep(5)
        response = httpx.get(
            f"{API}/storage/stores/{store['id']}",
            params=_params(),
            headers=_headers(token),
            timeout=30,
        )
        _check(response)
        store = response.json().get("store") or response.json()
    return store["id"]


def connect_database(token: str, config_id: str, store_id: str, project_id: str) -> None:
    """Put the database's keys on the project. Not sensitive, so they can be
    read back for the local tests."""
    response = httpx.post(
        f"{API}/v1/integrations/installations/{config_id}/resources/{store_id}/connections",
        params=_params(),
        headers=_headers(token),
        json={
            "projectId": project_id,
            "envVarEnvironments": ENVIRONMENTS,
            "makeEnvVarsSensitive": False,
        },
        timeout=60,
    )
    _check(response)


def read_env(token: str, project_id: str) -> dict[str, str]:
    """Every environment variable on the project, decrypted."""
    response = httpx.get(
        f"{API}/v10/projects/{project_id}/env",
        params=_params(),
        headers=_headers(token),
        timeout=30,
    )
    _check(response)
    env = {}
    for item in response.json().get("envs", []):
        one = httpx.get(
            f"{API}/v1/projects/{project_id}/env/{item['id']}",
            params=_params(),
            headers=_headers(token),
            timeout=30,
        )
        _check(one)
        env[item["key"]] = one.json().get("value", "")
    return env


def provision(token: str, name: str, config_id: str) -> dict[str, str]:
    """A new database connected to the project `name`, and its keys."""
    project_id = create_project(token, name)
    store_id = create_database(token, name, config_id)
    connect_database(token, config_id, store_id, project_id)
    env = read_env(token, project_id)
    missing = [key for key in (*PUBLIC_KEYS, MIGRATION_URL_KEY) if not env.get(key)]
    if missing:
        raise RuntimeError(f"The new database has no {', '.join(missing)}")
    return env


def write_env_file(job_dir: Path, env: dict[str, str]) -> None:
    """Only the browser keys go into the workspace, for the local build. The
    deploy step never uploads .env files."""
    lines = [f"{key}={env[key]}" for key in PUBLIC_KEYS]
    (Path(job_dir) / ".env.local").write_text("\n".join(lines) + "\n")


def migration_files(job_dir: Path) -> list[Path]:
    return sorted((Path(job_dir) / "supabase" / "migrations").glob("*.sql"))


def wait_for_connection(database_url: str, connect=psycopg.connect, timeout: int = 120):
    """A new database is reported available a little before Postgres accepts
    connections, so connecting is retried. Errors in the SQL itself are not."""
    deadline = time.monotonic() + timeout
    delay = 2
    while True:
        try:
            return connect(database_url, autocommit=False)
        except psycopg.OperationalError:
            if time.monotonic() + delay > deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 15)


def apply_migrations(database_url: str, job_dir: Path, connect=psycopg.connect) -> list[str]:
    """Run each migration in its own transaction, in file name order. Raises
    with the file's name when one fails, and stops there."""
    applied = []
    for path in migration_files(job_dir):
        try:
            with wait_for_connection(database_url, connect) as conn:
                conn.execute(path.read_text())
        except Exception as error:
            raise RuntimeError(f"{path.name}: {error}") from error
        applied.append(path.name)
    return applied
