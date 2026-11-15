import json

from agents.deploy import app_name
from agents.load_app import NO_SPEC, NOT_FOUND, after_load_app, make_load_app, planning_prompt
from tools.spec import read_spec, write_spec

HISTORY = [{"job_id": "j1", "prompt": "A guestbook where visitors leave notes", "at": "x"}]


def fake_download(token, deployment, dest):
    (dest / "spec").mkdir(exist_ok=True)
    (dest / "spec" / "history.json").write_text(json.dumps(HISTORY))
    (dest / "src" / "App.jsx").write_text("export default function App() {}")
    migrations = dest / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "001_tables.sql").write_text("create table notes ();")
    return []


def change(tmp_path, **kw):
    state = {
        "job_id": "26-11-15-1-abcdef1234",
        "prompt": "Add a dark mode",
        "app_name": "gb-311a1a",
    }
    load = make_load_app(
        tmp_path,
        "tok",
        find=kw.get("find", lambda t, n: "dpl_1"),
        download=kw.get("download", fake_download),
    )
    return load(state)


def test_new_apps_pass_through(tmp_path):
    assert make_load_app(tmp_path, None)({"job_id": "j", "prompt": "A timer"}) == {}
    assert after_load_app({}) == "analyst"


def test_a_change_loads_the_live_app_and_plans_from_its_history(tmp_path):
    out = change(tmp_path)
    job_dir = tmp_path / "26-11-15-1-abcdef1234"
    assert out["workspace_dir"] == str(job_dir)
    assert (job_dir / "src" / "App.jsx").read_text() == "export default function App() {}"
    assert (job_dir / "package.json").exists()  # template files under the app's own
    assert out["change_request"] == "Add a dark mode"
    assert "A guestbook where visitors leave notes" in out["prompt"]
    assert out["prompt"].endswith("Add a dark mode")
    assert out["applied_migrations"] == ["001_tables.sql"]
    assert after_load_app(out) == "analyst"


def test_an_app_that_is_not_live_ends_the_job(tmp_path):
    out = change(tmp_path, find=lambda t, n: None)
    assert out == {"errors": [NOT_FOUND.format(name="gb-311a1a")]}
    assert after_load_app(out) == "__end__"


def test_an_app_without_a_spec_cannot_be_changed(tmp_path):
    out = change(tmp_path, download=lambda t, d, dest: [])
    assert out == {"errors": [NO_SPEC.format(name="gb-311a1a")]}


def test_a_change_keeps_the_apps_name_and_adds_only_the_change_to_history(tmp_path):
    state = {"app_name": "gb-311a1a", "job_id": "j2", "requirements": {"app_summary": "x"}}
    assert app_name(state) == "gb-311a1a"
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "history.json").write_text(json.dumps(HISTORY))
    write_spec(
        tmp_path,
        {
            **state,
            "prompt": planning_prompt(HISTORY, "Add a dark mode"),
            "change_request": "Add a dark mode",
        },
        now=0,
    )
    assert [h["prompt"] for h in read_spec(tmp_path)["history"]] == [
        "A guestbook where visitors leave notes",
        "Add a dark mode",
    ]
