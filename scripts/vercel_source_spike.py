"""Read-only check of the Vercel source download against a real app."""
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, "backend")
from tools import vercel  # noqa: E402

token = os.environ["VERCEL_TOKEN"]
r = httpx.get(f"{vercel.API}/v9/projects", params=vercel._params({"search": "vyskar-", "limit": "20"}),
              headers=vercel._headers(token), timeout=30)
print("projects", r.status_code)
projects = [p for p in r.json().get("projects", []) if (p.get("targets") or {}).get("production")]
print("with production:", [p["name"] for p in projects])
name = projects[0]["name"].removeprefix("vyskar-")
dpl = vercel.production_deployment(token, name)
print("app", name, "deployment", dpl)
t = httpx.get(f"{vercel.API}/v6/deployments/{dpl}/files", params=vercel._params(), headers=vercel._headers(token), timeout=30)
print("tree status", t.status_code)
tree = t.json()
def show(entries, depth=0):
    for e in entries[:12]:
        print("  " * depth, e.get("type"), e.get("name"), "uid" if e.get("uid") else "")
        if depth < 1 and e.get("children"):
            show(e["children"], depth + 1)
show(tree if isinstance(tree, list) else [tree])
def first_file(entries):
    for e in entries:
        if e.get("type") == "file":
            return e
        f = first_file(e.get("children") or [])
        if f:
            return f
f = first_file(tree)
c = httpx.get(f"{vercel.API}/v8/deployments/{dpl}/files/{f['uid']}", params=vercel._params(), headers=vercel._headers(token), timeout=30)
print("file", f["name"], c.status_code, c.headers.get("content-type"))
try:
    body = c.json()
    print("json keys", list(body) if isinstance(body, dict) else type(body).__name__)
except Exception:
    print("raw bytes", len(c.content))
with tempfile.TemporaryDirectory() as d:
    written = vercel.download_source(token, dpl, Path(d))
    print("written", len(written), sorted(written)[:30])
    pkg = Path(d) / "package.json"
    print("package.json parses:", pkg.exists() and bool(json.loads(pkg.read_text())))
