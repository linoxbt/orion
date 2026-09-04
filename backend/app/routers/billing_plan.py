"""The plan an account is on, and how to change it.

Free accounts get a monthly allowance of bills; paid accounts get no limit.
The distinction is enforced where the work happens (bill ingestion), not here -
this router only reports the state and takes the payment.

Nothing in here upgrades an account on the browser's say-so. The redirect back
from the payment page is a hint that something may have changed; the account
moves only when Paystack's signed webhook arrives, or when this server asks
Paystack directly whether a reference was really paid.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.models import UserProfile
from app.security import require_user_id
from app.services import paystack, quota, supabase_store
from app.services.ratelimit import limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan", tags=["plan"])

PRO_DAYS = 30


class PlanState(BaseModel):
    plan: str
    unlimited: bool
    limit: int | None
    used: int
    remaining: int | None
    month: str
    price_usd: float
    expires_at: str | None
    can_upgrade: bool
    # So a renewal is never a surprise, and cancelling is possible from the app.
    renews: bool = False
    next_payment_at: str | None = None
    subscription_status: str | None = None


class UpgradeStarted(BaseModel):
    authorization_url: str
    reference: str


async def _profile(user_id: str) -> UserProfile:
    if not supabase_store.is_configured():
        raise HTTPException(status_code=503, detail="supabase_not_configured")
    return await supabase_store.get_profile(user_id) or UserProfile(id=user_id)


async def _grant_pro(
    user_id: str,
    reference: str,
    *,
    subscription_code: str | None = None,
    next_payment_at: str | None = None,
) -> None:
    """Move an account to pro, or extend it. Idempotent by payment reference.

    A webhook can be delivered more than once and the verify-on-return path can
    race it, so the same payment must never extend a plan twice. Each *new*
    payment - including the monthly renewals Paystack makes on its own - pushes
    the expiry out again.
    """
    profile = await supabase_store.get_profile(user_id) or UserProfile(id=user_id)
    if profile.payment_reference == reference:
        return

    profile.plan = "pro"
    profile.payment_reference = reference
    profile.plan_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=PRO_DAYS)
    ).isoformat()
    if subscription_code:
        profile.subscription_code = subscription_code
        profile.subscription_status = "active"
    if next_payment_at:
        profile.next_payment_at = next_payment_at
    await supabase_store.upsert_profile(profile)
    logger.info("Paid plan extended for %s on %s", user_id, reference)


async def _owner_of_subscription(code: str | None) -> str | None:
    """Which account a subscription belongs to.

    Subscription events do not carry our metadata, so the link back is the
    code recorded when the plan started.
    """
    if not code:
        return None
    profile = await supabase_store.find_profile_by_subscription(code)
    return profile.id if profile else None


async def _mark_subscription(user_id: str, status: str, next_payment_at: str | None = None) -> None:
    """Record what the subscription is doing without touching what was paid for.

    A cancelled subscription does not revoke the month already bought; it stops
    the next charge, and the plan lapses when its expiry passes.
    """
    profile = await supabase_store.get_profile(user_id)
    if profile is None:
        return
    profile.subscription_status = status
    if next_payment_at is not None:
        profile.next_payment_at = next_payment_at
    await supabase_store.upsert_profile(profile)


@router.get("", response_model=PlanState)
async def read_plan(user_id: str = Depends(require_user_id)) -> PlanState:
    profile = await _profile(user_id)
    return PlanState(
        **quota.describe(profile),
        can_upgrade=paystack.is_configured(),
        renews=profile.subscription_status == "active",
        next_payment_at=profile.next_payment_at,
        subscription_status=profile.subscription_status,
    )


@router.post("/upgrade", response_model=UpgradeStarted)
async def start_upgrade(user_id: str = Depends(require_user_id)) -> UpgradeStarted:
    if not paystack.is_configured():
        raise HTTPException(status_code=503, detail="payments_not_configured")

    # Each of these opens a transaction on Paystack. Unbounded, a loop fills
    # the merchant's dashboard with abandoned payments and risks being
    # throttled by them.
    limit(f"upgrade:{user_id}", max_calls=6, per_seconds=600)

    profile = await _profile(user_id)
    if not profile.email:
        raise HTTPException(
            status_code=422,
            detail="no_email: add an email address on your account page first.",
        )

    started = await paystack.start_upgrade(
        user_id=user_id,
        email=profile.email,
        amount=settings.pro_price,
        currency=settings.paystack_currency,
    )
    if not started.get("authorization_url"):
        raise HTTPException(status_code=502, detail="payment_start_failed")
    return UpgradeStarted(**started)


@router.post("/confirm", response_model=PlanState)
async def confirm_upgrade(
    reference: str, user_id: str = Depends(require_user_id)
) -> PlanState:
    """Check a payment the customer has just made.

    The reference comes from the browser, so it is verified against Paystack
    rather than believed, and the payment's own metadata decides which account
    is upgraded - not the caller.
    """
    if not paystack.is_configured():
        raise HTTPException(status_code=503, detail="payments_not_configured")

    # Verification is a third-party call keyed by a reference the browser
    # supplies, so it is trivially loopable without a cap.
    limit(f"confirm:{user_id}", max_calls=20, per_seconds=600)

    payment = await paystack.verify(reference)
    if payment is None:
        raise HTTPException(status_code=402, detail="payment_not_completed")

    paid_for = payment.get("user_id")
    if paid_for and paid_for != user_id:
        # Somebody else's payment reference. Refuse rather than upgrade either
        # account on it.
        logger.warning("Reference %s belongs to %s, not %s", reference, paid_for, user_id)
        raise HTTPException(status_code=403, detail="payment_belongs_to_another_account")

    await _grant_pro(user_id, reference)
    return PlanState(
        **quota.describe(await _profile(user_id)), can_upgrade=paystack.is_configured()
    )


@router.post("/webhook")
async def paystack_webhook(
    request: Request, x_paystack_signature: str | None = Header(default=None)
) -> dict[str, str]:
    """Paystack's own report on a payment or a subscription.

    This is the authority on what an account is entitled to. The raw body is
    what is signed, so it is read before any parsing.

    Handling the subscription lifecycle - not just the first charge - is what
    makes this a monthly plan rather than a one-off grant that lapses in
    silence a month later.
    """
    body = await request.body()
    if not paystack.signature_is_valid(body, x_paystack_signature):
        raise HTTPException(status_code=403, detail="invalid_signature")

    event = await request.json()
    kind = event.get("event")
    data = event.get("data") or {}

    # Paystack echoes our metadata on the transaction; subscription events
    # carry it on the nested customer or plan instead, so fall back to the
    # subscription code we recorded when the plan started.
    user_id = (data.get("metadata") or {}).get("user_id")

    if kind == "charge.success":
        reference = data.get("reference")
        if not user_id or not reference:
            logger.warning("charge.success with no user_id or reference: %s", reference)
            return {"status": "ignored"}
        await _grant_pro(
            user_id,
            reference,
            subscription_code=(data.get("plan") or {}).get("subscription_code"),
        )
        return {"status": "accepted"}

    if kind in ("subscription.create", "subscription.enable"):
        code = data.get("subscription_code")
        if user_id and code:
            await _mark_subscription(user_id, "active", data.get("next_payment_date"))
        return {"status": "accepted"}

    if kind in ("subscription.disable", "subscription.not_renew"):
        # The customer keeps the month they paid for; it simply stops renewing.
        code = data.get("subscription_code")
        owner = user_id or await _owner_of_subscription(code)
        if owner:
            await _mark_subscription(owner, "non-renewing", None)
        return {"status": "accepted"}

    if kind == "invoice.payment_failed":
        code = (data.get("subscription") or {}).get("subscription_code")
        owner = user_id or await _owner_of_subscription(code)
        if owner:
            logger.warning("Renewal payment failed for %s", owner)
            await _mark_subscription(owner, "attention")
        return {"status": "accepted"}

    return {"status": "ignored"}


@router.post("/cancel", response_model=PlanState)
async def cancel_plan(user_id: str = Depends(require_user_id)) -> PlanState:
    """Stop the plan renewing.

    Deliberately does not revoke access: the customer paid for this month and
    keeps it. The plan lapses when its expiry passes, which is what the free
    tier check already does on its own.
    """
    profile = await _profile(user_id)
    if not profile.subscription_code:
        raise HTTPException(status_code=409, detail="no_active_subscription")

    if not await paystack.cancel_subscription(profile.subscription_code):
        raise HTTPException(status_code=502, detail="cancel_failed")

    await _mark_subscription(user_id, "non-renewing", None)
    refreshed = await _profile(user_id)
    return PlanState(
        **quota.describe(refreshed),
        can_upgrade=paystack.is_configured(),
        renews=False,
        next_payment_at=refreshed.next_payment_at,
        subscription_status=refreshed.subscription_status,
    )
