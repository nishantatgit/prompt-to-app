"""A job read for its page is a snapshot: the build thread changing the live
job afterwards must not change, or break, what the page is reading."""

from api import jobs


def test_new_stage_does_not_change_a_job_already_read():
    jobs.create_job("snap-1", "a timer")
    jobs._step_started("snap-1", "guard")
    seen = jobs.get_job("snap-1")

    # The build thread moves on while the page is going through the stages.
    # Before the fix this raised "dictionary changed size during iteration".
    read = []
    for stage in seen["timings"]:
        read.append(stage)
        jobs._step_started("snap-1", "analyst")
        jobs._step_finished("snap-1", "guard")

    assert read == ["checking request"]
    assert list(seen["timings"]) == ["checking request"]
    assert seen["timings"]["checking request"]["finished"] is None


def test_page_view_works_while_a_stage_is_added():
    jobs.create_job("snap-2", "a timer")
    jobs._step_started("snap-2", "guard")
    seen = jobs.get_job("snap-2")
    jobs._step_started("snap-2", "architect")

    view = jobs.public_view(seen)
    assert list(view["timings"]["stages"]) == ["checking request"]
    assert list(jobs.public_view(jobs.get_job("snap-2"))["timings"]["stages"]) == [
        "checking request",
        "architecture",
    ]
