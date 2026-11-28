"""The SQLite stores and the trial ledger are made once per process, even
when the first requests after a restart arrive on several threads at once.
Two copies would each have their own lock (and the ledger its own copy of
the counts), so writes could be lost."""

import threading
import time
from types import SimpleNamespace

import pytest

from api import credits, feedback, jobs, push, routes

THREADS = 8


def _slow(cls):
    """A subclass whose setup takes a moment, so racing threads overlap."""

    class Slow(cls):
        made = 0

        def __init__(self, *args, **kwargs):
            time.sleep(0.05)
            type(self).made += 1
            super().__init__(*args, **kwargs)

    return Slow


def _call_together(factory, settings):
    barrier = threading.Barrier(THREADS)
    results = []

    def run():
        barrier.wait()
        results.append(factory(settings))

    threads = [threading.Thread(target=run) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


@pytest.mark.parametrize(
    "module, global_name, class_name, factory_name",
    [
        (credits, "_store", "CreditStore", "credit_store"),
        (feedback, "_store", "FeedbackStore", "feedback_store"),
        (push, "_store", "PushStore", "push_store"),
        (routes, "_ledger", "TrialLedger", "trial_ledger"),
    ],
)
def test_made_once_when_first_calls_race(
    module, global_name, class_name, factory_name, tmp_path, monkeypatch
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(module, global_name, None)
    slow = _slow(getattr(module, class_name))
    monkeypatch.setattr(module, class_name, slow)
    hooks_before = len(jobs.TRIAL_FINISHED_HOOKS)
    try:
        results = _call_together(
            getattr(module, factory_name), SimpleNamespace(workspaces_dir=tmp_path)
        )
        assert slow.made == 1
        assert len({id(r) for r in results}) == 1
        if module is routes:
            # The finished-app hook is added once, not once per racing call.
            assert len(jobs.TRIAL_FINISHED_HOOKS) == hooks_before + 1
    finally:
        del jobs.TRIAL_FINISHED_HOOKS[hooks_before:]
