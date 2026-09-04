"""Taking the upgrade payment.

Paystack rather than Stripe, for a concrete reason: Stripe does not support
Nigerian merchants, so a Nigerian business cannot hold a Stripe account at all.
Paystack is Stripe-owned, covers Nigeria, Ghana, Kenya, South Africa and Cote
d'Ivoire, and takes cards, bank transfer and USSD - which is what customers in
those markets actually pay with.

The only thing that upgrades an account is the signed webhook. A browser
returning from the payment page is a claim, not proof: anyone can request that
URL. So the redirect is treated as a hint to re-read the plan, and the account
changes only when Paystack tells the server directly, or when the server asks
Paystack to verify a reference itself.
"""

import hashlib
import hmac
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API = "https://api.paystack.co"

# Paystack settles in the currency of the account. Amounts are in the minor
# unit - kobo for NGN, cents for USD - so a whole-currency price is scaled.
MINOR_UNITS = 100


class PaystackNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.paystack_secret_key)


def _headers() -> dict[str, str]:
    if not settings.paystack_secret_key:
        raise PaystackNotConfigured("PAYSTACK_SECRET_KEY is not set")
    return {
        "Authorization": f"Bearer {settings.paystack_secret_key}",
        "content-type": "application/json",
    }


async def start_upgrade(user_id: str, email: str, amount: int, currency: str) -> dict:
    """Open a payment and hand back the page to send the customer to."""
    payload = {
        "email": email,
        "amount": amount * MINOR_UNITS,
        "currency": currency,
        # Echoed back on the webhook, so the payment can be matched to an
        # account without trusting anything the browser says.
        "metadata": {"user_id": user_id},
        "callback_url": f"{settings.public_app_url}/billing?upgraded=1",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(f"{API}/transaction/initialize", headers=_headers(), json=payload)
        res.raise_for_status()
        body = res.json()

    data = body.get("data") or {}
    return {"authorization_url": data.get("authorization_url"), "reference": data.get("reference")}


async def verify(reference: str) -> dict | None:
    """Ask Paystack directly whether a reference was actually paid.

    Used on the return from the payment page, so an upgrade does not have to
    wait for the webhook to arrive - while still never taking the browser's
    word for it.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(f"{API}/transaction/verify/{reference}", headers=_headers())
        if res.status_code == 404:
            return None
        res.raise_for_status()
        data = (res.json() or {}).get("data") or {}

    if data.get("status") != "success":
        return None
    return {
        "reference": data.get("reference"),
        "user_id": (data.get("metadata") or {}).get("user_id"),
        "amount": (data.get("amount") or 0) // MINOR_UNITS,
        "currency": data.get("currency"),
    }


def signature_is_valid(body: bytes, signature: str | None) -> bool:
    """Paystack signs the raw body with HMAC-SHA512 keyed by the secret key.

    Fails closed: an unconfigured deployment verifies nothing, so it must not
    accept an upgrade either.
    """
    if not settings.paystack_secret_key or not signature:
        return False
    expected = hmac.new(
        settings.paystack_secret_key.encode(), body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
