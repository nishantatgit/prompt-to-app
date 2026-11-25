"""Buying build credits with Razorpay.

Off until RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set. Packs come from
CREDIT_PACKS, a JSON list such as
  [{"id": "starter", "builds": 5, "price_inr": 499}]
so prices change without a code change. The defaults are placeholders.

CREDIT_PACKS is read on every build, so a mistyped value must not break
building: a pack that isn't valid is left out and logged as "bad_setting".
When none is valid, no packs are on sale (rather than the placeholder prices),
while bought builds can still be spent and restored.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.credits_store import CreditStore
from api.env import report_bad_setting
from api.limits import HourlyCounter, client_ip
from config import Settings, get_settings
from tools import razorpay

router = APIRouter(prefix="/api")

DEFAULT_PACKS = [
    {"id": "starter", "builds": 5, "price_inr": 499},
    {"id": "maker", "builds": 15, "price_inr": 1299},
]
VISITOR_HEADER = "x-vyskar-visitor"


def _whole(value) -> int | None:
    """A whole number of at least 1 from JSON: 5, 5.0 or "5"; else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return value if isinstance(value, int) and value >= 1 else None


def read_packs(raw: str | None) -> tuple:
    """The packs in CREDIT_PACKS, each as {"id", "builds", "price_inr"}.
    Unset or blank means the defaults. Bad packs are dropped and reported."""
    if raw is None or not raw.strip():
        return tuple(DEFAULT_PACKS)
    try:
        packs = json.loads(raw)
    except ValueError:
        report_bad_setting("CREDIT_PACKS", raw, problem="not_json", using="no packs")
        return ()
    if packs is None or packs == []:
        return tuple(DEFAULT_PACKS)
    if not isinstance(packs, list):
        report_bad_setting("CREDIT_PACKS", raw, problem="not_a_list", using="no packs")
        return ()
    good, seen = [], set()
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        pack_id = pack.get("id")
        builds, price = _whole(pack.get("builds")), _whole(pack.get("price_inr"))
        if isinstance(pack_id, str) and pack_id.strip() and builds and price:
            if pack_id not in seen:
                seen.add(pack_id)
                good.append({"id": pack_id, "builds": builds, "price_inr": price})
    if len(good) < len(packs):
        report_bad_setting(
            "CREDIT_PACKS",
            raw,
            problem="bad_packs",
            dropped=len(packs) - len(good),
            using=f"{len(good)} packs",
        )
    return tuple(good)


@dataclass(frozen=True)
class CreditConfig:
    key_id: str
    secret: str
    webhook_secret: str
    packs: tuple

    @property
    def enabled(self) -> bool:
        return bool(self.key_id and self.secret)

    def pack(self, pack_id: str) -> dict | None:
        return next((p for p in self.packs if p["id"] == pack_id), None)

    @classmethod
    def from_env(cls) -> "CreditConfig":
        return cls(
            key_id=os.getenv("RAZORPAY_KEY_ID", ""),
            secret=os.getenv("RAZORPAY_KEY_SECRET", ""),
            webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
            packs=read_packs(os.getenv("CREDIT_PACKS")),
        )


_store: CreditStore | None = None


def credit_store(settings: Settings) -> CreditStore:
    """One store per process. DATA_DIR is Fly's volume; without it, next to
    the workspaces (fine for tests, lost on deploy)."""
    global _store
    if _store is None:
        folder = os.getenv("DATA_DIR") or settings.workspaces_dir
        _store = CreditStore(Path(folder) / "credits.db")
    return _store


def open_store() -> CreditStore | None:
    """The store if this process has opened it, else None."""
    return _store


def visitor_of(request: Request) -> str:
    return request.headers.get(VISITOR_HEADER, "").strip()[:64]


def _config_or_503() -> CreditConfig:
    config = CreditConfig.from_env()
    if not config.enabled:
        raise HTTPException(status_code=503, detail="Buying builds isn't available yet.")
    return config


@router.get("/credits")
def credits_status(request: Request, settings: Settings = Depends(get_settings)):
    config = CreditConfig.from_env()
    if not config.enabled:
        return {"enabled": False, "builds_left": 0, "packs": []}
    return {
        "enabled": True,
        "builds_left": credit_store(settings).balance(visitor_of(request)),
        "packs": list(config.packs),
    }


class OrderRequest(BaseModel):
    pack: str


@router.post("/credits/order")
def create_order(req: OrderRequest, request: Request, settings: Settings = Depends(get_settings)):
    config = _config_or_503()
    visitor = visitor_of(request)
    if not visitor:
        raise HTTPException(status_code=400, detail="Reload the page and try again.")
    pack = config.pack(req.pack)
    if pack is None:
        raise HTTPException(status_code=400, detail="Unknown pack.")
    amount = pack["price_inr"] * 100  # Razorpay takes paise
    try:
        order = razorpay.create_order(
            config.key_id,
            config.secret,
            amount,
            receipt=f"{pack['id']}-{visitor[:20]}",
            notes={"visitor": visitor, "pack": pack["id"], "builds": str(pack["builds"])},
        )
    except Exception:
        raise HTTPException(
            status_code=502, detail="Couldn't start the payment. Try again."
        ) from None
    credit_store(settings).add_order(order["id"], visitor, pack["id"], pack["builds"], amount)
    return {
        "order_id": order["id"],
        "amount": amount,
        "currency": "INR",
        "key_id": config.key_id,
        "builds": pack["builds"],
    }


# Paid in Razorpay, but the check here failed for now: restoring with the
# payment ID adds the builds once Razorpay answers (see _record_unconfirmed).
UNCONFIRMED = (
    "Your payment went through, but Vyskar couldn't add the builds yet. "
    "Restore them with your payment ID in a minute."
)


class PaymentProof(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/credits/verify")
def verify_payment(
    proof: PaymentProof, request: Request, settings: Settings = Depends(get_settings)
):
    config = _config_or_503()
    store = credit_store(settings)
    order = store.order(proof.razorpay_order_id)
    if order is None or not razorpay.signature_matches(
        proof.razorpay_order_id, proof.razorpay_payment_id, proof.razorpay_signature, config.secret
    ):
        raise HTTPException(status_code=400, detail="This payment couldn't be verified.")
    try:
        razorpay.settle_payment(
            config.key_id,
            config.secret,
            proof.razorpay_payment_id,
            proof.razorpay_order_id,
            order["amount"],
        )
    except razorpay.PaymentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=UNCONFIRMED,
        ) from None
    store.record_payment(proof.razorpay_payment_id, proof.razorpay_order_id)
    return {
        "builds_left": store.balance(order["visitor"]),
        # Shown to keep: it restores these builds in another browser.
        "payment_id": proof.razorpay_payment_id,
    }


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, settings: Settings = Depends(get_settings)):
    """Adds credits even when the browser closed before verifying."""
    config = CreditConfig.from_env()
    body = await request.body()
    if not config.webhook_secret or not razorpay.webhook_matches(
        body, request.headers.get("x-razorpay-signature", ""), config.webhook_secret
    ):
        raise HTTPException(status_code=400, detail="bad signature")
    event = json.loads(body)
    if event.get("event") == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        store = credit_store(settings)
        order = store.order(payment.get("order_id", ""))
        if order and payment.get("amount") == order["amount"]:
            store.record_payment(payment["id"], payment["order_id"])
    return {"ok": True}


RESTORE_PER_HOUR = 10


def _record_unconfirmed(config: CreditConfig, store: CreditStore, payment_id: str) -> bool:
    """Count a payment Vyskar never confirmed, so it can be restored.

    Paying and confirming are two steps: if the confirm call failed (the
    phone lost signal, or Razorpay or Vyskar was slow) and no webhook came,
    the money was taken but the builds were never added, and restoring said
    "No builds found". Razorpay is asked about the payment instead: it must
    be for an order Vyskar created, for that order's amount, and captured
    (an authorized one is captured here, as in verify). Any problem means
    False, so restore answers as before."""
    try:
        payment = razorpay.get_payment(config.key_id, config.secret, payment_id)
        if payment.get("id") != payment_id:
            return False
        order_id = payment.get("order_id") or ""
        order = store.order(order_id)
        if order is None:
            return False
        razorpay.settle_payment(
            config.key_id, config.secret, payment_id, order_id, order["amount"]
        )
    except Exception:
        return False
    store.record_payment(payment_id, order_id)
    return True
_restore_hits = HourlyCounter()


class RestoreRequest(BaseModel):
    payment_id: str = Field(max_length=40, pattern=r"^pay_[A-Za-z0-9]+$")


@router.post("/credits/restore")
def restore_builds(
    req: RestoreRequest, request: Request, settings: Settings = Depends(get_settings)
):
    """Bring bought builds to this browser with the payment ID from the
    Razorpay receipt. Few tries per hour: payment IDs can't be guessed."""
    config = _config_or_503()
    if not _restore_hits.allow(client_ip(request), RESTORE_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many tries. Try again in an hour.")
    visitor = visitor_of(request)
    if not visitor:
        raise HTTPException(status_code=400, detail="Reload the page and try again.")
    store = credit_store(settings)
    payment_id = req.payment_id.strip()
    balance = store.restore(payment_id, visitor)
    if balance is None and _record_unconfirmed(config, store, payment_id):
        balance = store.restore(payment_id, visitor)
    if balance is None:
        raise HTTPException(
            status_code=404,
            detail="No builds found for that payment ID. Check your Razorpay receipt.",
        )
    return {"builds_left": balance}
