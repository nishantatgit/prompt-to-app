from api.trial import TrialConfig, TrialLedger, sweep_databases

ON = TrialConfig(builds_per_person=2, daily_cap=5)
DAY = 86_400


def ledger(tmp_path):
    return TrialLedger(tmp_path / "trial.json")


def test_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("FREE_TRIAL_BUILDS", raising=False)
    config = TrialConfig.from_env()
    assert not config.enabled
    assert ledger(tmp_path).builds_left(config, "v1", "1.1.1.1") == 0


def test_each_person_gets_their_builds(tmp_path):
    book = ledger(tmp_path)
    assert book.builds_left(ON, "v1", "1.1.1.1", now=0) == 2
    book.record_build("v1", "1.1.1.1", now=0)
    book.record_build("v1", "1.1.1.1", now=1)
    assert book.builds_left(ON, "v1", "1.1.1.1", now=2) == 0
    assert book.builds_left(ON, "v2", "2.2.2.2", now=2) == 2


def test_a_shared_ip_gets_three_people_worth(tmp_path):
    roomy = TrialConfig(builds_per_person=2, daily_cap=100)
    book = ledger(tmp_path)
    for i in range(6):
        book.record_build(f"v{i // 2}", "9.9.9.9", now=i)
    assert book.builds_left(roomy, "new-person", "9.9.9.9", now=10) == 0
    assert book.builds_left(roomy, "new-person", "8.8.8.8", now=10) == 2


def test_the_daily_cap_covers_everyone_and_resets_next_day(tmp_path):
    book = ledger(tmp_path)
    for i in range(5):
        book.record_build(f"v{i}", f"10.0.0.{i}", now=i)
    assert book.builds_left(ON, "v9", "10.0.0.9", now=10) == 0
    assert book.builds_left(ON, "v9", "10.0.0.9", now=DAY + 10) == 2


def test_no_visitor_id_means_no_trial(tmp_path):
    assert ledger(tmp_path).builds_left(ON, "", "1.1.1.1") == 0


def test_counts_survive_a_restart(tmp_path):
    ledger(tmp_path).record_build("v1", "1.1.1.1", now=0)
    assert ledger(tmp_path).builds_left(ON, "v1", "1.1.1.1", now=1) == 1


def test_a_damaged_file_starts_fresh(tmp_path):
    (tmp_path / "trial.json").write_text("{not json")
    assert ledger(tmp_path).builds_left(ON, "v1", "1.1.1.1") == 2


def test_trial_databases_are_deleted_after_a_day(tmp_path):
    book = ledger(tmp_path)
    book.record_database("old-app", now=0)
    book.record_database("new-app", now=DAY)
    deleted = []

    assert sweep_databases(book, deleted.append, now=DAY + 60) == ["old-app"]
    assert deleted == ["old-app"]
    assert book.expired_databases(now=DAY + 60) == []
    assert book.expired_databases(now=2 * DAY + 60) == ["new-app"]


def test_a_failed_delete_is_tried_again_next_time(tmp_path):
    book = ledger(tmp_path)
    book.record_database("old-app", now=0)

    def fail(name):
        raise RuntimeError("Vercel 500")

    assert sweep_databases(book, fail, now=DAY + 1) == []
    assert book.expired_databases(now=DAY + 1) == ["old-app"]
