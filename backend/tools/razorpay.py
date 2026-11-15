"""Razorpay: orders, payment checks and webhooks, for buying build credits.

Standard Checkout: the server creates an order, the browser pays it in
Razorpay's checkout, and the server checks the payment before adding
credits: the signature Razorpay returns, then the payment itself.
"""

import hashlib
import hmac

import httpx

API = "https://api.razorpay.com/v1"


class PaymentError(Exception):
    """The payment can't be accepted; the message says why."""


def _auth(key_id: str, secret: str) -> tuple[str, str]:
    return (key_id, secret)


def create_order(key_id: str, secret: str, amount_paise: int, receipt: str, notes: dict) -> dict:
    response = httpx.post(
        f"{API}/orders",
        auth=_auth(key_id, secret),
        json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def signature_matches(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """Checkout's proof that this payment belongs to this order."""
    expected = hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def webhook_matches(body: bytes, signature: str, webhook_secret: str) -> bool:
    expected = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def settle_payment(key_id: str, secret: str, payment_id: str, order_id: str, amount: int) -> dict:
    """Make sure the money is taken: the payment must be for this order and
    amount, and captured. An authorized payment is captured here."""
    response = httpx.get(f"{API}/payments/{payment_id}", auth=_auth(key_id, secret), timeout=30)
    response.raise_for_status()
    payment = response.json()
    if payment.get("order_id") != order_id or payment.get("amount") != amount:
        raise PaymentError("This payment does not match the order.")
    if payment.get("status") == "authorized":
        response = httpx.post(
            f"{API}/payments/{payment_id}/capture",
            auth=_auth(key_id, secret),
            json={"amount": amount, "currency": "INR"},
            timeout=30,
        )
        response.raise_for_status()
        payment = response.json()
    if payment.get("status") != "captured":
        raise PaymentError("The payment did not go through.")
    return payment
