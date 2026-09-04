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


def channels() -> list[str]:
    """The payment methods to offer, in order.

    A channel the account is not approved for is ignored rather than rejected,
    so card can sit at the front of this list before it is enabled and start
    appearing the moment it is. What fails is a list with nothing active in it,
    which is why this falls back rather than returning empty.
    """
    named = [c.strip() for c in settings.paystack_channels.split(",") if c.strip()]
    return named or ["card", "bank", "ussd", "bank_transfer"]


def _headers() -> dict[str, str]:
    if not settings.paystack_secret_key:
        raise PaystackNotConfigured("PAYSTACK_SECRET_KEY is not set")
    return {
        "Authorization": f"Bearer {settings.paystack_secret_key}",
        "content-type": "application/json",
    }


# One plan per (name, amount, currency, interval). Cached so the dashboard is
# not littered with a new plan on every upgrade.
_plan_code: str | None = None

PLAN_NAME = "Orion Unlimited"


async def ensure_plan(amount: int, currency: str) -> str | None:
    """The monthly plan a subscription is created against.

    Reused rather than recreated: Paystack keeps every plan ever made, and a
    fresh one per checkout would make the merchant's dashboard unreadable and
    the subscriptions impossible to reason about.

    Returns None if the plan cannot be established, in which case the caller
    falls back to a one-off charge rather than failing the upgrade outright.
    """
    global _plan_code
    if _plan_code:
        return _plan_code
    if settings.paystack_plan_code:
        _plan_code = settings.paystack_plan_code
        return _plan_code

    want = amount * MINOR_UNITS
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            listed = await client.get(
                f"{API}/plan", headers=_headers(), params={"perPage": 100}
            )
            listed.raise_for_status()
            for plan in (listed.json() or {}).get("data") or []:
                if (
                    plan.get("name") == PLAN_NAME
                    and plan.get("amount") == want
                    and plan.get("currency") == currency
                    and plan.get("interval") == "monthly"
                ):
                    _plan_code = plan.get("plan_code")
                    return _plan_code

            created = await client.post(
                f"{API}/plan",
                headers=_headers(),
                json={
                    "name": PLAN_NAME,
                    "amount": want,
                    "currency": currency,
                    "interval": "monthly",
                },
            )
            created.raise_for_status()
            _plan_code = ((created.json() or {}).get("data") or {}).get("plan_code")
            logger.info("Created Paystack plan %s", _plan_code)
            return _plan_code
        except Exception as exc:  # noqa: BLE001 - fall back to a one-off charge
            logger.warning("Could not establish a Paystack plan: %s", exc)
            return None


async def cancel_subscription(subscription_code: str, email_token: str | None = None) -> bool:
    """Stop a subscription renewing. The customer keeps what they paid for."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        if not email_token:
            fetched = await client.get(
                f"{API}/subscription/{subscription_code}", headers=_headers()
            )
            if fetched.status_code != 200:
                return False
            email_token = ((fetched.json() or {}).get("data") or {}).get("email_token")

        res = await client.post(
            f"{API}/subscription/disable",
            headers=_headers(),
            json={"code": subscription_code, "token": email_token},
        )
        return res.status_code == 200


async def start_upgrade(user_id: str, email: str, amount: int, currency: str) -> dict:
    """Open a payment and hand back the page to send the customer to.

    Attached to a monthly plan, so Paystack creates a subscription on success
    and charges again each month. Without the plan this was a single charge
    dressed up as a subscription: it granted thirty days and then lapsed in
    silence.
    """
    payload = {
        "email": email,
        "amount": amount * MINOR_UNITS,
        "currency": currency,
        # Echoed back on the webhook, so the payment can be matched to an
        # account without trusting anything the browser says.
        "metadata": {"user_id": user_id},
        # Without this Paystack decides for itself and a new account tends to
        # show bank transfer alone. Naming the channels puts card first and
        # offers the alternatives people in these markets actually use.
        "channels": channels(),
        # No query string of our own. Paystack appends "?trxref=..&reference=.."
        # verbatim, so a URL that already carries a "?" ends up with two, and
        # the first existing parameter swallows trxref:
        #   /billing?upgraded=1?trxref=T1&reference=T1
        #   -> upgraded="1?trxref=T1"
        # reference still parses, so this happened to work, but only because
        # the page reads reference before trxref.
        "callback_url": f"{settings.public_app_url}/billing",
    }
    plan_code = await ensure_plan(amount, currency)
    if plan_code:
        # With a plan attached Paystack sets up the subscription itself and
        # ignores the amount, taking it from the plan.
        payload["plan"] = plan_code

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
