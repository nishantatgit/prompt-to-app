from api import jobs


class Clock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


def started(name):
    return ("tasks", {"id": name, "name": name, "input": {}, "triggers": ()})


def finished(name, result=None):
    return ("tasks", {"id": name, "name": name, "result": result or {}, "error": None, "interrupts": []})


class TimedGraph:
    """Yields events, moving the clock forward by the given seconds first."""

    def __init__(self, clock, events):
        self.clock = clock
        self.events = events

    def stream(self, state, config, stream_mode):
        assert "tasks" in stream_mode
        for seconds, event in self.events:
            self.clock.now += seconds
            yield event


def test_each_stage_gets_its_time(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(jobs.time, "time", clock)
    jobs.create_job("t-1", "a timer")
    graph = TimedGraph(
        clock,
        [
            (0, started("guard")),
            (3, finished("guard")),
            (0, ("updates", {"guard": {"allowed": True}})),
            (0, started("analyst")),
            (12, finished("analyst")),
            # Building and test planning overlap; building spans both of its steps.
            (0, started("builder")),
            (0, started("test_planner")),
            (20, finished("test_planner")),
            (40, finished("builder")),
            (0, started("migrations")),
            (5, finished("migrations")),
            (0, started("deploy")),
            (30, finished("deploy")),
            (0, ("updates", {"deploy": {"deploy_url": "https://x.vyskar.app"}})),
        ],
    )
    jobs._run(graph, "t-1", "a timer", 50)

    view = jobs.public_view(jobs.get_job("t-1"))["timings"]
    assert view["stages"]["checking request"] == {"seconds": 3.0, "running": False}
    assert view["stages"]["requirements"] == {"seconds": 12.0, "running": False}
    assert view["stages"]["building"] == {"seconds": 65.0, "running": False}
    assert view["stages"]["planning tests"] == {"seconds": 20.0, "running": False}
    assert view["stages"]["deploying"] == {"seconds": 30.0, "running": False}
    assert view["total_seconds"] == 110.0


def test_a_running_stage_counts_up_to_now(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(jobs.time, "time", clock)
    jobs.create_job("t-2", "a timer")
    jobs._update("t-2", status="running", started_at=clock.now)
    jobs._step_started("t-2", "architect")
    clock.now += 7
    view = jobs.public_view(jobs.get_job("t-2"))["timings"]
    assert view["stages"]["architecture"] == {"seconds": 7.0, "running": True}
    assert view["total_seconds"] == 7.0


def test_a_failed_build_stops_every_clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(jobs.time, "time", clock)
    jobs.create_job("t-3", "a timer")

    class Failing:
        def stream(self, state, config, stream_mode):
            yield started("architect")
            clock.now += 4
            raise RuntimeError("boom")

    jobs._run(Failing(), "t-3", "a timer", 50)
    clock.now += 100  # time passing after the failure must not count
    view = jobs.public_view(jobs.get_job("t-3"))["timings"]
    assert view["stages"]["architecture"] == {"seconds": 4.0, "running": False}
    assert view["total_seconds"] == 4.0


def test_steps_outside_the_shown_stages_are_ignored(monkeypatch):
    jobs.create_job("t-4", "a timer")
    jobs._step_started("t-4", "__start__")
    jobs._step_finished("t-4", "__start__")
    assert jobs.get_job("t-4")["timings"] == {}
