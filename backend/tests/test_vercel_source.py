import base64

import httpx

from tools import vercel

FILES = {"uid_pkg": b'{"name": "notes"}', "uid_app": b"export default 1", "uid_spec": b"[]"}
TREE = [
    {
        "name": "src",
        "type": "directory",
        "mode": 0,
        "children": [
            {"name": "package.json", "type": "file", "mode": 0, "uid": "uid_pkg"},
            {
                "name": "src",
                "type": "directory",
                "mode": 0,
                "children": [{"name": "App.jsx", "type": "file", "mode": 0, "uid": "uid_app"}],
            },
            {
                "name": "spec",
                "type": "directory",
                "mode": 0,
                "children": [
                    {"name": "history.json", "type": "file", "mode": 0, "uid": "uid_spec"}
                ],
            },
        ],
    }
]


def fake_get(projects):
    def get(url, **kwargs):
        path = url.replace(vercel.API, "")
        request = httpx.Request("GET", url)
        if path.startswith("/v9/projects/"):
            name = path.rsplit("/", 1)[1]
            if name not in projects:
                return httpx.Response(404, json={}, request=request)
            return httpx.Response(200, json=projects[name], request=request)
        if path == "/v6/deployments/dpl_1/files":
            return httpx.Response(200, json=TREE, request=request)
        uid = path.rsplit("/", 1)[1]
        data = base64.b64encode(FILES[uid]).decode()
        return httpx.Response(200, json={"data": data}, request=request)

    return get


def test_finds_the_deployment_live_at_the_apps_address(monkeypatch):
    projects = {"vyskar-notes": {"targets": {"production": {"id": "dpl_1"}}}}
    monkeypatch.setattr(vercel.httpx, "get", fake_get(projects))
    assert vercel.production_deployment("t", "notes") == "dpl_1"
    assert vercel.production_deployment("t", "never-built") is None


def test_downloads_the_source_with_its_spec(monkeypatch, tmp_path):
    monkeypatch.setattr(vercel.httpx, "get", fake_get({}))
    written = vercel.download_source("t", "dpl_1", tmp_path)
    assert sorted(written) == ["package.json", "spec/history.json", "src/App.jsx"]
    assert (tmp_path / "src/App.jsx").read_bytes() == b"export default 1"
    assert (tmp_path / "spec/history.json").read_bytes() == b"[]"


def test_deploys_now_carry_the_spec(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/history.json").write_text("[]")
    (tmp_path / ".env.local").write_text("SECRET=1")
    files = [f["file"] for f in vercel.collect_files(tmp_path)]
    assert files == ["spec/history.json"]
