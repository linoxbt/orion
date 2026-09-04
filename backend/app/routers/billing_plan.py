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
    price_usd: int
    expires_at: str | None
    can_upgrade: bool


class UpgradeStarted(BaseModel):
    authorization_url: str
    reference: str


async def _profile(user_id: str) -> UserProfile:
    if not supabase_store.is_configured():
        raise HTTPException(status_code=503, detail="supabase_not_configured")
    return await supabase_store.get_profile(user_id) or UserProfile(id=user_id)


async def _grant_pro(user_id: str, reference: str) -> None:
    """Move an account to pro. Idempotent by payment reference.

    A webhook can be delivered more than once, and the verify-on-return path
    can race it, so the same payment must not extend the subscription twice.
    """
    profile = await supabase_store.get_profile(user_id) or UserProfile(id=user_id)
    if profile.payment_reference == reference:
        return

    profile.plan = "pro"
    profile.payment_reference = reference
    profile.plan_expires_at = (
        datetime.now(timezone.utc) + timedelta(days=PRO_DAYS)
    ).isoformat()
    await supabase_store.upsert_profile(profile)
    logger.info("Upgraded %s to pro on %s", user_id, reference)


@router.get("", response_model=PlanState)
async def read_plan(user_id: str = Depends(require_user_id)) -> PlanState:
    state = quota.describe(await _profile(user_id))
    return PlanState(**state, can_upgrade=paystack.is_configured())


@router.post("/upgrade", response_model=UpgradeStarted)
async def start_upgrade(user_id: str = Depends(require_user_id)) -> UpgradeStarted:
    if not paystack.is_configured():
        raise HTTPException(status_code=503, detail="payments_not_configured")

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
    """Paystack's own report that a payment succeeded.

    This is the authority. The raw body is what is signed, so it is read
    before any parsing.
    """
    body = await request.body()
    if not paystack.signature_is_valid(body, x_paystack_signature):
        raise HTTPException(status_code=403, detail="invalid_signature")

    event = await request.json()
    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    data = event.get("data") or {}
    user_id = (data.get("metadata") or {}).get("user_id")
    reference = data.get("reference")
    if not user_id or not reference:
        logger.warning("charge.success with no user_id or reference: %s", reference)
        return {"status": "ignored"}

    await _grant_pro(user_id, reference)
    return {"status": "accepted"}
