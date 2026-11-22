import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import jobs, push
from api.push import (
    PushConfig,
    PushStore,
    build_message,
    generate_keys,
    is_push_service,
    push_job_finished,
)

ON = PushConfig(public_key="pub", private_key="priv", subject="https://vyskar.com")
OFF = PushConfig(public_key="", private_key="", subject="https://vyskar.com")


def subscription(n=1):
    return {"endpoint": f"https://push.example/{n}", "keys": {"p256dh": f"p{n}", "auth": f"a{n}"}}


def finished(job_id="job-1", status="succeeded", **state):
    return {"job_id": job_id, "status": status, "state": state}


class Recorder:
    def __init__(self, fail=None):
        self.sent = []
        self.fail = fail or {}

    def __call__(self, sub, payload, config):
        status = self.fail.get(sub["endpoint"])
        if status:
            raise RuntimeError("push failed") if status == "boom" else Error(status)
        self.sent.append((sub, json.loads(payload)))


class Error(Exception):
    def __init__(self, status):
        super().__init__(f"push service said {status}")
        self.response = SimpleNamespace(status_code=status)


# Settings


def test_push_is_off_until_both_keys_are_set(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    assert PushConfig.from_env().enabled is False
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    config = PushConfig.from_env()
    assert config.enabled is True
    assert config.subject == "https://vyskar.com"


def test_generated_keys_are_a_p256_pair():
    public, private = generate_keys()
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    import base64

    assert len(base64.urlsafe_b64decode(pad(public))) == 65  # uncompressed point
    assert len(base64.urlsafe_b64decode(pad(private))) == 32
    from py_vapid import Vapid

    assert Vapid.from_string(private) is not None  # pywebpush can read it


# Messages


def test_a_live_app_opens_from_the_notification():
    message = build_message(finished(deploy_url="https://tip.vercel.app", confidence=92))
    assert message == {
        "title": "Your app is live",
        "body": "Tests passed: 92%. Tap to open it.",
        "url": "https://tip.vercel.app",
        "tag": "job-1",
    }


def test_a_stopped_build_opens_vyskar():
    for status in ("failed", "rejected"):
        message = build_message(finished(status=status))
        assert message["title"] == "Your build stopped"
        assert message["url"] == "/"


def test_a_cancelled_build_is_not_pushed():
    assert build_message(finished(status="cancelled")) is None


# Store and sending


def test_each_watcher_gets_one_push(tmp_path):
    store = PushStore(tmp_path / "push.db")
    for n in (1, 2):
        sub = subscription(n)
        store.watch("job-1", sub["endpoint"], **sub["keys"])
    store.watch("job-1", subscription(1)["endpoint"], "p1", "a1")  # watched twice
    send = Recorder()

    assert push_job_finished(finished(deploy_url="https://x.app"), store, ON, send) == 2
    assert sorted(s["endpoint"] for s, _ in send.sent) == [
        "https://push.example/1",
        "https://push.example/2",
    ]
    assert send.sent[0][1]["url"] == "https://x.app"
    # Pushed once: finishing again sends nothing.
    assert push_job_finished(finished(), store, ON, send) == 0


def test_only_the_jobs_watchers_are_pushed(tmp_path):
    store = PushStore(tmp_path / "push.db")
    store.watch("job-2", **{"endpoint": "https://push.example/2", "p256dh": "p", "auth": "a"})
    send = Recorder()
    assert push_job_finished(finished("job-1"), store, ON, send) == 0
    assert push_job_finished(finished("job-2"), store, ON, send) == 1


def test_a_gone_subscription_is_forgotten_and_others_still_sent(tmp_path):
    store = PushStore(tmp_path / "push.db")
    for n in (1, 2, 3):
        sub = subscription(n)
        store.watch("job-1", sub["endpoint"], **sub["keys"])
    send = Recorder(fail={"https://push.example/1": 410, "https://push.example/2": "boom"})

    assert push_job_finished(finished(), store, ON, send) == 1
    assert store.count() == 2  # the 410 one is gone, the timed out one stays


def test_nothing_is_sent_when_push_is_off(tmp_path):
    store = PushStore(tmp_path / "push.db")
    store.watch("job-1", "https://push.example/1", "p", "a")
    send = Recorder()
    assert push_job_finished(finished(), store, OFF, send) == 0
    assert send.sent == []


def test_subscriptions_survive_a_restart(tmp_path):
    PushStore(tmp_path / "push.db").watch("job-1", "https://push.example/1", "p", "a")
    store = PushStore(tmp_path / "push.db")
    assert store.count() == 1
    assert len(store.take_watchers("job-1")) == 1


def at(monkeypatch, seconds):
    monkeypatch.setattr(push.time, "time", lambda: seconds)


def test_a_watch_left_from_a_job_that_never_finished_is_forgotten(tmp_path, monkeypatch):
    # A job cut off by a restart never finishes, so its watch is never taken.
    store = PushStore(tmp_path / "push.db")
    at(monkeypatch, 1_000)
    store.watch("lost-job", "https://push.example/1", "p1", "a1")
    store.watch("lost-job", "https://push.example/2", "p2", "a2")

    at(monkeypatch, 1_000 + push.STALE_SECONDS + 1)
    store.watch("new-job", "https://push.example/2", "p2", "a2")

    assert store.take_watchers("lost-job") == []
    # Subscription 1 was not used since and is gone; 2 watches the new job.
    assert store.count() == 1
    assert [w["endpoint"] for w in store.take_watchers("new-job")] == ["https://push.example/2"]


def test_recent_watches_and_subscriptions_are_kept(tmp_path, monkeypatch):
    store = PushStore(tmp_path / "push.db")
    at(monkeypatch, 1_000)
    store.watch("job-1", "https://push.example/1", "p1", "a1")
    assert store.take_watchers("job-1")  # pushed: the subscription watches nothing now

    at(monkeypatch, 1_000 + push.STALE_SECONDS - 1)
    store.watch("job-2", "https://push.example/2", "p2", "a2")
    store.watch("job-3", "https://push.example/3", "p3", "a3")

    assert store.count() == 3
    assert len(store.take_watchers("job-2")) == 1


def test_using_a_subscription_again_keeps_it(tmp_path, monkeypatch):
    store = PushStore(tmp_path / "push.db")
    at(monkeypatch, 1_000)
    store.watch("job-1", "https://push.example/1", "p1", "a1")
    store.take_watchers("job-1")

    at(monkeypatch, 1_000 + push.STALE_SECONDS - 10)
    store.watch("job-2", "https://push.example/1", "p1", "a1")  # same browser, new build
    store.take_watchers("job-2")

    at(monkeypatch, 1_000 + push.STALE_SECONDS + 10)
    store.watch("job-3", "https://push.example/9", "p9", "a9")
    assert store.count() == 2  # used within the day, so subscription 1 stays


# Jobs call the hook when they finish


class FakeGraph:
    def __init__(self, url):
        self.url = url

    def stream(self, state, config, stream_mode):
        yield "updates", {"deploy": {"deploy_url": self.url}}


def test_a_finished_job_runs_the_finished_hooks(monkeypatch):
    seen = []
    monkeypatch.setattr(jobs, "JOB_FINISHED_HOOKS", [seen.append, lambda job: 1 / 0])
    jobs.create_job("push-job", "a timer")
    jobs._run(FakeGraph("https://timer.vercel.app"), "push-job", "a timer", 10)
    assert [job["status"] for job in seen] == ["succeeded"]
    assert seen[0]["state"]["deploy_url"] == "https://timer.vercel.app"


# Endpoints


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = SimpleNamespace(workspaces_dir=tmp_path)
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv-key")
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setattr(push, "_store", None)
    app.dependency_overrides[push.get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_status_gives_the_public_key(client, monkeypatch):
    assert client.get("/api/push").json() == {"enabled": True, "public_key": "pub-key"}
    monkeypatch.delenv("VAPID_PRIVATE_KEY")
    assert client.get("/api/push").json() == {"enabled": False, "public_key": ""}


def test_only_browser_push_services_are_known():
    assert is_push_service("https://fcm.googleapis.com/fcm/send/abc")
    assert is_push_service("https://web.push.apple.com/QF1")
    assert is_push_service("https://updates.push.services.mozilla.com/wpush/v2/x")
    assert is_push_service("https://wns2-pn1p.notify.windows.com/w/?token=x")
    assert not is_push_service("http://fcm.googleapis.com/fcm/send/abc")
    assert not is_push_service("https://fcm.googleapis.com.evil.example/x")
    assert not is_push_service("https://evilpush.apple.com.example/x")
    assert not is_push_service("https://fcm.googleapis.com:8443/x")
    assert not is_push_service("https://localhost/x")


def browser_subscription():
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
        "keys": {"p256dh": "p", "auth": "a"},
    }


def test_subscribing_watches_the_job(client, tmp_path):
    jobs.create_job("watched-job", "a timer")
    response = client.post(
        "/api/push/subscribe",
        json={"job_id": "watched-job", "subscription": browser_subscription()},
    )
    assert response.status_code == 200
    assert (tmp_path / "push.db").exists()
    assert len(push._store.take_watchers("watched-job")) == 1


def test_subscribing_to_an_unknown_job_fails(client):
    response = client.post(
        "/api/push/subscribe", json={"job_id": "nope", "subscription": browser_subscription()}
    )
    assert response.status_code == 404


def test_only_https_push_services_are_accepted(client):
    jobs.create_job("watched-job-2", "a timer")
    sub = {**browser_subscription(), "endpoint": "https://169.254.169.254/latest"}
    response = client.post(
        "/api/push/subscribe", json={"job_id": "watched-job-2", "subscription": sub}
    )
    assert response.status_code == 422


def test_subscribing_while_push_is_off_fails(client, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY")
    jobs.create_job("watched-job-3", "a timer")
    response = client.post(
        "/api/push/subscribe",
        json={"job_id": "watched-job-3", "subscription": browser_subscription()},
    )
    assert response.status_code == 503


def finish(job_id, status, **state):
    jobs._update(job_id, status=status, state=state)


def test_a_build_that_finished_before_subscribing_is_pushed_at_once(client, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(push, "_send", recorder)
    jobs.create_job("quick-job", "a timer")
    finish("quick-job", "succeeded", deploy_url="https://timer.vercel.app", confidence=100)
    response = client.post(
        "/api/push/subscribe",
        json={"job_id": "quick-job", "subscription": browser_subscription()},
    )
    assert response.status_code == 200
    assert len(recorder.sent) == 1
    assert recorder.sent[0][1]["url"] == "https://timer.vercel.app"
    assert push._store.take_watchers("quick-job") == []  # nothing left behind


def test_a_cancelled_build_leaves_no_watch_behind(client, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(push, "_send", recorder)
    jobs.create_job("cancelled-job", "a timer")
    jobs.cancel_job("cancelled-job")
    client.post(
        "/api/push/subscribe",
        json={"job_id": "cancelled-job", "subscription": browser_subscription()},
    )
    assert recorder.sent == []
    assert push._store.take_watchers("cancelled-job") == []


def test_a_running_build_is_not_pushed_on_subscribe(client, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(push, "_send", recorder)
    jobs.create_job("running-job", "a timer")
    jobs._update("running-job", status="running")
    client.post(
        "/api/push/subscribe",
        json={"job_id": "running-job", "subscription": browser_subscription()},
    )
    assert recorder.sent == []
    assert len(push._store.take_watchers("running-job")) == 1
