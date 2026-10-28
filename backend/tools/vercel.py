import base64
import time
from pathlib import Path

import httpx

API = "https://api.vercel.com"
SKIP_DIRS = {"node_modules", "dist", "tests", "test-results", "playwright-report", ".git"}
SKIP_FILES = {"playwright-results.json", "test-report.json"}
DONE_STATES = {"READY", "ERROR", "CANCELED"}

import os


def _params(extra: dict | None = None) -> dict:
    params = dict(extra or {})
    team_id = os.environ.get("VERCEL_TEAM_ID")
    if team_id:
        params["teamId"] = team_id
    return params


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _check(response: httpx.Response) -> None:
    if response.is_error:
        raise RuntimeError(f"Vercel {response.status_code}: {response.text}")


def build_log(token: str, deployment_id: str, max_chars: int = 4000) -> str:
    response = httpx.get(
        f"{API}/v3/deployments/{deployment_id}/events",
        params=_params({"builds": "1", "limit": "-1"}),
        headers=_headers(token),
        timeout=30,
    )
    _check(response)
    lines = []
    for event in response.json():
        text = event.get("text") or (event.get("payload") or {}).get("text")
        if text:
            lines.append(text)
    return "\n".join(lines)[-max_chars:]


def collect_files(job_dir: Path) -> list[dict]:
    """Every source file in the job folder, base64 encoded, without build or test output."""
    files = []
    for path in sorted(Path(job_dir).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(job_dir)
        if SKIP_DIRS & set(rel.parts) or rel.name in SKIP_FILES:
            continue
        files.append(
            {
                "file": rel.as_posix(),
                "data": base64.b64encode(path.read_bytes()).decode(),
                "encoding": "base64",
            }
        )
    return files


def create_deployment(token: str, name: str, files: list[dict]) -> dict:
    """Start a production deployment. Vercel installs and builds the project itself."""
    response = httpx.post(
        f"{API}/v13/deployments",
        params={"skipAutoDetectionConfirmation": "1"},
        headers=_headers(token),
        json={
            "name": name,
            "files": files,
            "target": "production",
            "projectSettings": {
                "framework": "vite",
                "installCommand": "yarn install",
                "buildCommand": "yarn build",
                "outputDirectory": "dist",
            },
        },
        timeout=60,
    )
    _check(response)
    return response.json()


def wait_until_ready(token: str, deployment_id: str, timeout: int = 300, interval: int = 5) -> dict:
    """Poll until the deployment is READY, ERROR or CANCELED."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = httpx.get(
            f"{API}/v13/deployments/{deployment_id}",
            headers=_headers(token),
            timeout=30,
        )
        _check(response)
        deployment = response.json()
        if deployment["readyState"] in DONE_STATES:
            return deployment
        time.sleep(interval)
    raise TimeoutError(f"deployment {deployment_id} not ready after {timeout}s")


def add_domain(token: str, project: str, domain: str) -> dict:
    """Attach a domain, such as converter.vyskar.app, to a project."""
    response = httpx.post(
        f"{API}/v10/projects/{project}/domains",
        headers=_headers(token),
        json={"name": domain},
        timeout=30,
    )
    _check(response)
    return response.json()


def deploy_app(token: str, job_dir: Path, name: str, root_domain: str = "vyskar.app") -> str:
    """Deploy a job folder and return its public URL, such as https://converter.vyskar.app."""
    project = f"vyskar-{name}"
    deployment = create_deployment(token, project, collect_files(job_dir))
    result = wait_until_ready(token, deployment["id"])
    if result["readyState"] != "READY":
        log = build_log(token, deployment["id"])
        raise RuntimeError(f"deployment {deployment['id']} ended as {result['readyState']}:\n{log}")
    domain = f"{name}.{root_domain}"
    add_domain(token, project, domain)
    return f"https://{domain}"
