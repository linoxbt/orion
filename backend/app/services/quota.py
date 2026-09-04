"""How many bills a free account may negotiate this month.

Free accounts get a fixed number of bills per calendar month; paid accounts get
no limit. The allowance covers the bill and everything that follows from it -
extraction, the negotiation, the calls - because a bill is the unit of work a
customer actually thinks in.

The month is stored beside the count rather than derived from a timestamp, so
nothing has to run on the first of the month for the allowance to come back.
A count belonging to a month that is not this one is simply stale.
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.models import UserProfile
from app.services import supabase_store

logger = logging.getLogger(__name__)

FREE_MONTHLY_BILLS = 5
PRO_PRICE_USD = 15


def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _plan_is_live(profile: UserProfile) -> bool:
    """Paid, and not lapsed.

    An expiry in the past means the subscription was not renewed, so the
    account is treated as free again without anything having to sweep the
    table.
    """
    if profile.plan != "pro":
        return False
    if not profile.plan_expires_at:
        return True
    try:
        expires = datetime.fromisoformat(profile.plan_expires_at.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Unparseable plan_expires_at for %s", profile.id)
        return True
    return expires > datetime.now(timezone.utc)


def used_this_month(profile: UserProfile) -> int:
    return profile.bills_used if profile.quota_month == current_month() else 0


def describe(profile: UserProfile) -> dict:
    """What the account page and the upgrade prompt need to say."""
    pro = _plan_is_live(profile)
    used = used_this_month(profile)
    return {
        "plan": "pro" if pro else "free",
        "unlimited": pro,
        "limit": None if pro else FREE_MONTHLY_BILLS,
        "used": used,
        "remaining": None if pro else max(0, FREE_MONTHLY_BILLS - used),
        "month": current_month(),
        "price_usd": PRO_PRICE_USD,
        "expires_at": profile.plan_expires_at if pro else None,
    }


async def consume_bill(user_id: str) -> None:
    """Count one bill against the allowance, or refuse.

    Called before the work is done rather than after, so an account cannot
    spend quota it does not have by running several extractions at once.
    """
    if not supabase_store.is_configured():
        # Without a store there is nowhere to keep a count. Refusing every
        # upload over a missing integration would be worse than not metering.
        return

    profile = await supabase_store.get_profile(user_id) or UserProfile(id=user_id)

    if _plan_is_live(profile):
        return

    used = used_this_month(profile)
    if used >= FREE_MONTHLY_BILLS:
        raise HTTPException(
            status_code=402,
            detail=(
                f"free_limit_reached: {FREE_MONTHLY_BILLS} bills a month on the free "
                f"plan. Upgrade for unlimited bills at ${PRO_PRICE_USD} a month."
            ),
        )

    profile.bills_used = used + 1
    profile.quota_month = current_month()
    await supabase_store.upsert_profile(profile)
