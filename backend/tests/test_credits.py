import hashlib
import hmac
import json
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from api import credits, routes
from api.credits_store import CreditStore
from tools import razorpay

SECRET = "rzp_secret"
WEBHOOK_SECRET = "whsec"


def sign(order_id, payment_id, secret=SECRET):
    return hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()


# The store


def test_a_payment_adds_its_order_builds_once(tmp_path):
    store = CreditStore(tmp_path / "credits.db")
    store.add_order("order_1", "visitor-1", "starter", 5, 49900)
    assert store.record_payment("pay_1", "order_1") is True
    assert store.record_payment("pay_1", "order_1") is False  # browser and webhook both report it
    assert store.record_payment("pay_2", "order_unknown") is False
    assert store.balance("visitor-1") == 5
    assert store.balance("visitor-2") == 0


def test_credits_survive_a_restart(tmp_path):
    store = CreditStore(tmp_path / "credits.db")
    store.add_order("order_1", "v", "starter", 5, 49900)
    store.record_payment("pay_1", "order_1")
    store.use("v", "job-1")
    assert CreditStore(tmp_path / "credits.db").balance("v") == 4


def test_a_refund_gives_back_one_build_once(tmp_path):
    store = CreditStore(tmp_path / "credits.db")
    store.add_order("order_1", "v", "starter", 5, 49900)
    store.record_payment("pay_1", "order_1")
    store.use("v", "job-1")
    assert store.refund("job-1") is True
    assert store.refund("job-1") is False  # a second cancel gives nothing more
    assert store.refund("job-unknown") is False
    assert store.balance("v") == 5


def test_the_last_credit_can_be_spent_only_once(tmp_path):
    store = CreditStore(tmp_path / "credits.db")
    store.add_order("order_1", "v", "one", 1, 9900)
    store.record_payment("pay_1", "order_1")
    results = []
    threads = [
        threading.Thread(target=lambda i=i: results.append(store.use("v", f"job-{i}")))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert store.balance("v") == 0


# Razorpay checks


def test_signatures():
    assert razorpay.signature_matches("order_1", "pay_1", sign("order_1", "pay_1"), SECRET)
    assert not razorpay.signature_matches("order_1", "pay_2", sign("order_1", "pay_1"), SECRET)
    body = b'{"event":"payment.captured"}'
    good = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert razorpay.webhook_matches(body, good, WEBHOOK_SECRET)
    assert not razorpay.webhook_matches(body + b" ", good, WEBHOOK_SECRET)
    # Junk with non-ASCII characters is refused, not a TypeError.
    assert not razorpay.signature_matches("order_1", "pay_1", "café", SECRET)
    assert not razorpay.webhook_matches(body, "café", WEBHOOK_SECRET)


def fake_razorpay(monkeypatch, status="captured", order_id="order_1", amount=49900):
    calls = []

    def get(url, **kw):
        calls.append(("GET", url))
        return httpx.Response(
            200,
            json={"id": "pay_1", "order_id": order_id, "amount": amount, "status": status},
            request=httpx.Request("GET", url),
        )

    def post(url, **kw):
        calls.append(("POST", url))
        return httpx.Response(
            200,
            json={"id": "pay_1", "order_id": order_id, "amount": amount, "status": "captured"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(razorpay.httpx, "get", get)
    monkeypatch.setattr(razorpay.httpx, "post", post)
    return calls


def test_an_authorized_payment_is_captured(monkeypatch):
    calls = fake_razorpay(monkeypatch, status="authorized")
    razorpay.settle_payment("k", SECRET, "pay_1", "order_1", 49900)
    assert calls[-1] == ("POST", f"{razorpay.API}/payments/pay_1/capture")


def test_a_payment_for_another_order_or_amount_is_refused(monkeypatch):
    fake_razorpay(monkeypatch, amount=100)
    with pytest.raises(razorpay.PaymentError):
        razorpay.settle_payment("k", SECRET, "pay_1", "order_1", 49900)


def test_a_failed_payment_is_refused(monkeypatch):
    fake_razorpay(monkeypatch, status="failed")
    with pytest.raises(razorpay.PaymentError):
        razorpay.settle_payment("k", SECRET, "pay_1", "order_1", 49900)


# Endpoints


@pytest.fixture
def client(tmp_path, monkeypatch):
    from api.main import app

    settings = SimpleNamespace(
        workspaces_dir=tmp_path,
        builder_mode="loop",
        graph_recursion_limit=50,
        api_key_for=lambda provider: "sk-ant-vyskar",
    )
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", SECRET)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.delenv("CREDIT_PACKS", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("ALLOW_SERVER_KEYS", raising=False)
    monkeypatch.delenv("STUB_LLM", raising=False)
    monkeypatch.setattr(credits, "_store", None)
    monkeypatch.setattr(
        razorpay, "create_order", lambda key_id, secret, amount, receipt, notes: {"id": "order_1"}
    )
    started = []
    monkeypatch.setattr(routes, "check_key", lambda provider, key: None)
    monkeypatch.setattr(routes, "check_rate_limit", lambda request: None)
    monkeypatch.setattr(routes, "has_capacity", lambda: True)
    monkeypatch.setattr(
        routes, "make_models", lambda provider, key, s, meter=None: started.append((provider, key))
    )
    monkeypatch.setattr(routes, "build_graph", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "submit", lambda *a: None)
    app.dependency_overrides[routes.get_settings] = lambda: settings
    app.dependency_overrides[credits.get_settings] = lambda: settings
    app.dependency_overrides[routes.get_agent_limits] = lambda: None
    c = TestClient(app, headers={"X-Vyskar-Visitor": "visitor-1"})
    c.started = started
    yield c
    app.dependency_overrides.clear()


def buy(client, monkeypatch):
    fake_razorpay(monkeypatch)
    order = client.post("/api/credits/order", json={"pack": "starter"}).json()
    proof = {
        "razorpay_order_id": order["order_id"],
        "razorpay_payment_id": "pay_1",
        "razorpay_signature": sign(order["order_id"], "pay_1"),
    }
    return order, proof


def test_credits_are_off_without_razorpay_keys(client, monkeypatch):
    monkeypatch.delenv("RAZORPAY_KEY_SECRET")
    assert client.get("/api/credits").json() == {"enabled": False, "builds_left": 0, "packs": []}
    assert client.post("/api/credits/order", json={"pack": "starter"}).status_code == 503


def test_buying_a_pack(client, monkeypatch):
    status = client.get("/api/credits").json()
    assert status["enabled"] and status["builds_left"] == 0
    assert [p["id"] for p in status["packs"]] == ["starter", "maker"]
    order, proof = buy(client, monkeypatch)
    assert order["amount"] == 49900 and order["key_id"] == "rzp_test_key"
    assert client.post("/api/credits/verify", json=proof).json()["builds_left"] == 5
    # Reporting the same payment again adds nothing.
    assert client.post("/api/credits/verify", json=proof).json()["builds_left"] == 5


def test_packs_and_prices_come_from_settings(client, monkeypatch):
    monkeypatch.setenv("CREDIT_PACKS", json.dumps([{"id": "trial", "builds": 2, "price_inr": 99}]))
    assert client.get("/api/credits").json()["packs"] == [
        {"id": "trial", "builds": 2, "price_inr": 99}
    ]
    assert client.post("/api/credits/order", json={"pack": "starter"}).status_code == 400


def test_a_forged_payment_adds_nothing(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    proof["razorpay_signature"] = sign(proof["razorpay_order_id"], "pay_1", secret="guess")
    assert client.post("/api/credits/verify", json=proof).status_code == 400
    assert client.get("/api/credits").json()["builds_left"] == 0


def test_a_non_ascii_signature_is_refused_not_a_crash(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    proof["razorpay_signature"] = "café"
    assert client.post("/api/credits/verify", json=proof).status_code == 400
    webhook = client.post(
        "/api/razorpay/webhook",
        content=b"{}",
        headers={"X-Razorpay-Signature": "café".encode("latin-1")},
    )
    assert webhook.status_code == 400
    assert client.get("/api/credits").json()["builds_left"] == 0


def test_the_webhook_adds_credits_when_the_browser_closed(client, monkeypatch):
    buy(client, monkeypatch)
    event = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_1", "order_id": "order_1", "amount": 49900}}},
    }
    body = json.dumps(event).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    bad = client.post("/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": "x"})
    assert bad.status_code == 400
    ok = client.post(
        "/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": signature}
    )
    assert ok.status_code == 200
    assert client.get("/api/credits").json()["builds_left"] == 5


def test_a_paid_build_runs_on_vyskars_key_and_spends_one_credit(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    response = client.post("/api/build", json={"prompt": "A timer", "provider": "openai"})
    assert response.status_code == 202
    assert client.started == [("anthropic", "sk-ant-vyskar")]
    assert client.get("/api/credits").json()["builds_left"] == 4


def test_a_bought_build_cancelled_in_the_queue_is_given_back(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    job_id = client.post("/api/build", json={"prompt": "A timer", "provider": "openai"}).json()[
        "job_id"
    ]
    assert client.get("/api/credits").json()["builds_left"] == 4
    # submit is stubbed, so the job is still waiting for a builder.
    view = client.post(f"/api/jobs/{job_id}/cancel").json()
    assert view["status"] == "cancelled"
    assert view["credit_refunded"] is True
    assert client.get("/api/credits").json()["builds_left"] == 5
    assert client.get(f"/api/jobs/{job_id}").json()["credit_refunded"] is True


def test_a_bought_build_cancelled_after_it_started_stays_spent(client, monkeypatch):
    from api import jobs

    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    job_id = client.post("/api/build", json={"prompt": "A timer", "provider": "openai"}).json()[
        "job_id"
    ]
    jobs._update(job_id, status="running")  # the model may already have been called
    view = client.post(f"/api/jobs/{job_id}/cancel").json()
    assert view["status"] == "cancelled"
    assert view["credit_refunded"] is False
    assert client.get("/api/credits").json()["builds_left"] == 4


def test_cancelling_an_own_key_build_touches_no_credits(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    job_id = client.post(
        "/api/build", json={"prompt": "A timer", "provider": "openai", "api_key": "sk-own"}
    ).json()["job_id"]
    view = client.post(f"/api/jobs/{job_id}/cancel").json()
    assert view["credit_refunded"] is False
    assert client.get("/api/credits").json()["builds_left"] == 5


def test_your_own_key_never_spends_credits(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    client.post("/api/credits/verify", json=proof)
    client.post("/api/build", json={"prompt": "A timer", "provider": "openai", "api_key": "sk-own"})
    assert client.started == [("openai", "sk-own")]
    assert client.get("/api/credits").json()["builds_left"] == 5


def test_without_credits_or_a_key_a_build_is_refused(client):
    response = client.post("/api/build", json={"prompt": "A timer", "provider": "openai"})
    assert response.status_code == 400


# Restoring bought builds in another browser


def test_builds_move_to_a_new_browser_with_the_payment_id(tmp_path):
    store = CreditStore(tmp_path / "credits.db")
    store.add_order("order_1", "old-browser", "starter", 5, 49900)
    store.record_payment("pay_1", "order_1")
    store.use("old-browser", "job-1")
    assert store.restore("pay_1", "new-browser") == 4
    assert store.balance("old-browser") == 0
    assert store.restore("pay_1", "new-browser") == 4  # again: nothing changes
    assert store.restore("pay_unknown", "new-browser") is None


def test_restoring_over_the_api(client, monkeypatch):
    _, proof = buy(client, monkeypatch)
    assert client.post("/api/credits/verify", json=proof).json() == {
        "builds_left": 5,
        "payment_id": "pay_1",
    }
    other = TestClient(client.app, headers={"X-Vyskar-Visitor": "visitor-2"})
    assert other.get("/api/credits").json()["builds_left"] == 0
    assert other.post("/api/credits/restore", json={"payment_id": "pay_1"}).json() == {
        "builds_left": 5
    }
    assert client.get("/api/credits").json()["builds_left"] == 0
    assert other.post("/api/credits/restore", json={"payment_id": "pay_nope"}).status_code == 404
    assert other.post("/api/credits/restore", json={"payment_id": "order_1"}).status_code == 422


def test_restore_tries_are_limited(client, monkeypatch):
    monkeypatch.setattr(credits, "RESTORE_PER_HOUR", 2)
    credits._restore_hits.clear()
    for _ in range(2):
        assert client.post("/api/credits/restore", json={"payment_id": "pay_x1"}).status_code == 404
    assert client.post("/api/credits/restore", json={"payment_id": "pay_x1"}).status_code == 429
