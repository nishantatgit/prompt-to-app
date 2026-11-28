"""Runs the real tools/screenshot.cjs against a local server.

Needs node and a Playwright with its Chromium. The test points the script at
whichever Playwright node can find, and skips itself when there is none, as
on CI, where the backend job installs no browsers.
"""

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tools.screenshot import SCRIPT

PAGE = b"<!doctype html><title>Notes</title><h1>My notes</h1>"


def find_playwright() -> str | None:
    if shutil.which("node") is None:
        return None
    for name in ("@playwright/test", "playwright"):
        found = subprocess.run(
            ["node", "-e", f"console.log(require.resolve({json.dumps(name)}))"],
            capture_output=True,
            text=True,
        )
        if found.returncode == 0:
            return found.stdout.strip()
    return None


PLAYWRIGHT = find_playwright()
pytestmark = pytest.mark.skipif(PLAYWRIGHT is None, reason="no Playwright for node")


@pytest.fixture
def workspace(tmp_path):
    """An app workspace whose node_modules has @playwright/test, like a real build's."""
    package = tmp_path / "ws" / "node_modules" / "@playwright" / "test"
    package.mkdir(parents=True)
    (package / "index.js").write_text(f"module.exports = require({json.dumps(PLAYWRIGHT)});\n")
    (package / "package.json").write_text('{"name": "@playwright/test", "main": "index.js"}\n')
    return tmp_path / "ws"


@pytest.fixture
def server():
    """A site that answers 404 for its first `failures` visits, then the page."""
    state = {"failures": 0, "visits": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_response(404)
                self.end_headers()
                return
            state["visits"] += 1
            ok = state["visits"] > state["failures"]
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE if ok else b"<h1>404: DEPLOYMENT_NOT_FOUND</h1>")

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_address[1]}/"
    yield state
    httpd.shutdown()


def photograph(workspace, url, out):
    env = {**os.environ, "SCREENSHOT_RETRY_MS": "200"}
    return subprocess.run(
        ["node", str(SCRIPT), url, str(out)],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_a_live_page_is_photographed(workspace, server, tmp_path):
    out = tmp_path / "shot.jpg"
    result = photograph(workspace, server["url"], out)
    assert result.returncode == 0, result.stderr
    assert out.read_bytes()[:2] == b"\xff\xd8"  # a JPEG
    assert server["visits"] == 1


def test_a_domain_that_404s_at_first_is_tried_again(workspace, server, tmp_path):
    server["failures"] = 2
    out = tmp_path / "shot.jpg"
    result = photograph(workspace, server["url"], out)
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert server["visits"] == 3


def test_an_error_page_is_never_saved_as_the_app(workspace, server, tmp_path):
    server["failures"] = 99
    out = tmp_path / "shot.jpg"
    result = photograph(workspace, server["url"], out)
    assert result.returncode != 0
    assert "answered 404" in result.stderr
    assert not out.exists()
    assert server["visits"] == 3


def test_nothing_answering_is_a_failure(workspace, tmp_path):
    out = tmp_path / "shot.jpg"
    result = photograph(workspace, "http://127.0.0.1:9/", out)
    assert result.returncode != 0
    assert "could not open" in result.stderr
    assert not out.exists()
