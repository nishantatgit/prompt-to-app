"""Buying build credits with Razorpay.

Off until RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set. Packs come from
CREDIT_PACKS, a JSON list such as
  [{"id": "starter", "builds": 5, "price_inr": 499}]
so prices change without a code change. The defaults are placeholders.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.credits_store import CreditStore
from api.limits import HourlyCounter, client_ip
from config import Settings, get_settings
from tools import razorpay

router = APIRouter(prefix="/api")

DEFAULT_PACKS = [
    {"id": "starter", "builds": 5, "price_inr": 499},
    {"id": "maker", "builds": 15, "price_inr": 1299},
]
VISITOR_HEADER = "x-vyskar-visitor"


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
        packs = json.loads(os.getenv("CREDIT_PACKS") or "null") or DEFAULT_PACKS
        return cls(
            key_id=os.getenv("RAZORPAY_KEY_ID", ""),
            secret=os.getenv("RAZORPAY_KEY_SECRET", ""),
            webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET", ""),
            packs=tuple(packs),
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
    amount = int(pack["price_inr"]) * 100  # Razorpay takes paise
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
            detail="Payment received; your builds will appear in a minute.",
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
_restore_hits = HourlyCounter()


class RestoreRequest(BaseModel):
    payment_id: str = Field(max_length=40, pattern=r"^pay_[A-Za-z0-9]+$")


@router.post("/credits/restore")
def restore_builds(
    req: RestoreRequest, request: Request, settings: Settings = Depends(get_settings)
):
    """Bring bought builds to this browser with the payment ID from the
    Razorpay receipt. Few tries per hour: payment IDs can't be guessed."""
    _config_or_503()
    if not _restore_hits.allow(client_ip(request), RESTORE_PER_HOUR):
        raise HTTPException(status_code=429, detail="Too many tries. Try again in an hour.")
    visitor = visitor_of(request)
    if not visitor:
        raise HTTPException(status_code=400, detail="Reload the page and try again.")
    balance = credit_store(settings).restore(req.payment_id.strip(), visitor)
    if balance is None:
        raise HTTPException(
            status_code=404,
            detail="No builds found for that payment ID. Check your Razorpay receipt.",
        )
    return {"builds_left": balance}
