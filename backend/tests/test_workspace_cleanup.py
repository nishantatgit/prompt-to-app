from pathlib import Path

from api import jobs, routes
from tools.workspace import BUILD_OUTPUT, remove_build_output, sweep_build_output


def make_job_dir(root: Path, job_id: str) -> Path:
    job_dir = root / job_id
    (job_dir / "src").mkdir(parents=True)
    (job_dir / "src" / "App.jsx").write_text("export default function App() {}")
    (job_dir / "package.json").write_text("{}")
    for name in BUILD_OUTPUT:
        (job_dir / name).mkdir()
        (job_dir / name / "file.js").write_text("x")
    return job_dir


def test_remove_build_output_keeps_the_source(tmp_path):
    job_dir = make_job_dir(tmp_path, "a")
    remove_build_output(job_dir)
    for name in BUILD_OUTPUT:
        assert not (job_dir / name).exists()
    assert (job_dir / "src" / "App.jsx").exists()
    assert (job_dir / "package.json").exists()


def test_remove_build_output_never_follows_a_link(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    job_dir = tmp_path / "ws" / "a"
    job_dir.mkdir(parents=True)
    (job_dir / "node_modules").symlink_to(outside, target_is_directory=True)
    remove_build_output(job_dir)
    assert not (job_dir / "node_modules").exists()
    assert (outside / "keep.txt").read_text() == "keep"


def test_sweep_skips_running_jobs_and_other_files(tmp_path):
    done = make_job_dir(tmp_path, "done")
    running = make_job_dir(tmp_path, "running")
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots" / "done.jpg").write_text("jpg")
    (tmp_path / "trial-usage.json").write_text("{}")

    cleaned = sweep_build_output(tmp_path, lambda job_id: job_id == "running")

    assert cleaned == ["done"]
    assert not (done / "node_modules").exists()
    assert (running / "node_modules" / "file.js").exists()
    assert (tmp_path / "screenshots" / "done.jpg").exists()
    assert (tmp_path / "trial-usage.json").exists()
    # Nothing left to clean: a second sweep does nothing.
    assert sweep_build_output(tmp_path, lambda job_id: False) == ["running"]
    assert sweep_build_output(tmp_path, lambda job_id: False) == []


def test_sweep_of_a_missing_folder_does_nothing(tmp_path):
    assert sweep_build_output(tmp_path / "nope", lambda job_id: False) == []


class OneStepGraph:
    """A graph whose only step sets up the workspace and deploys."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def stream(self, state, config, stream_mode=None):
        yield (
            "updates",
            {"deploy": {"workspace_dir": str(self.workspace), "deploy_url": "https://x.app"}},
        )


def test_a_finished_build_cleans_its_folder_and_older_ones(tmp_path):
    assert routes._clean_finished_workspaces in jobs.JOB_FINISHED_HOOKS
    older = make_job_dir(tmp_path, "older-job")  # left from before a restart
    jobs.create_job("other-running", "prompt")
    jobs._update("other-running", status="running")
    running = make_job_dir(tmp_path, "other-running")
    mine = make_job_dir(tmp_path, "clean-1")
    jobs.create_job("clean-1", "prompt")

    jobs._run(OneStepGraph(mine), "clean-1", "prompt", 50)

    assert jobs.get_job("clean-1")["status"] == "succeeded"
    assert not (mine / "node_modules").exists()
    assert (mine / "src" / "App.jsx").exists()
    assert not (older / "node_modules").exists()
    assert (running / "node_modules").exists()
    jobs.cancel_job("other-running")


def test_a_build_stopped_before_its_folder_cleans_nothing(tmp_path, monkeypatch):
    swept = []
    monkeypatch.setattr(routes, "sweep_build_output", lambda *args: swept.append(args) or [])
    jobs.create_job("clean-2", "prompt")
    jobs._run(RejectGraph(), "clean-2", "prompt", 50)
    assert jobs.get_job("clean-2")["status"] == "rejected"
    assert swept == []


class RejectGraph:
    def stream(self, state, config, stream_mode=None):
        yield ("updates", {"guard": {"allowed": False, "guard_reason": "no"}})
