"""Public proof of a saving, and the renewals worth calling about again.

Two things that only make sense once a negotiation has actually finished:

  GET /api/receipts/{task_id}   a shareable, public record of what was saved
  GET /api/renewals             bills whose promotional period is about to end

The receipt is deliberately public and deliberately thin. It carries the
provider, the before and after, and the confirmation number - and nothing else.
No phone number, no account details, no transcript, no bill. A link someone
forwards to a friend must not become a way to read a stranger's account.

Renewals exist because a negotiated rate expires. The extraction already reads
contract_end_date off the bill, and the month before it lapses is the moment a
second call is worth making - which is what turns Orion from a one-off tool
into something with a reason to exist next month.
"""

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.security import require_user_id
from app.store import get_session, list_sessions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["receipts"])

RENEWAL_WINDOW_DAYS = 45


class Receipt(BaseModel):
    """What a saving looks like to someone who wasn't on the call."""

    provider: str
    previous_rate: float | None
    new_rate: float | None
    monthly_saving: float | None
    annual_saving: float | None
    confirmation_number: str | None
    outcome: str | None
    verified: bool
    verification_source: str | None
    # A seeded example. Without this a worked sample would produce a public,
    # shareable receipt asserting a saving that never happened.
    is_sample: bool = False


@router.get("/api/receipts/{task_id}", response_model=Receipt)
async def get_receipt(task_id: str) -> Receipt:
    """A shareable record of a verified saving. Public, and intentionally so -
    but only ever for a negotiation that was actually verified, and carrying
    nothing that identifies the customer."""
    session = await get_session(task_id)
    if session is None:
        raise HTTPException(status_code=404, detail="not_found")

    # An unverified negotiation has nothing to prove, and publishing one would
    # be a claim the transcript doesn't support.
    if not session.verified:
        raise HTTPException(status_code=404, detail="no_verified_outcome")

    monthly = None
    if session.previous_rate is not None and session.new_rate is not None:
        monthly = round(session.previous_rate - session.new_rate, 2)

    return Receipt(
        provider=session.provider,
        previous_rate=session.previous_rate,
        new_rate=session.new_rate,
        monthly_saving=monthly,
        annual_saving=round(monthly * 12, 2) if monthly is not None else None,
        confirmation_number=session.confirmation_number,
        outcome=session.outcome,
        verified=session.verified,
        verification_source=session.verification_source,
        is_sample=session.is_sample,
    )


class Renewal(BaseModel):
    task_id: str
    provider: str
    contract_end_date: str
    days_remaining: int
    current_rate: float | None
    negotiated_rate: float | None


def _parse_day(value: str) -> date | None:
    """Bills print dates in whatever format they like; take the ISO-ish ones
    and ignore the rest rather than failing the whole listing."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


@router.get("/api/renewals", response_model=list[Renewal])
async def list_renewals(
    within_days: int = RENEWAL_WINDOW_DAYS, user_id: str = Depends(require_user_id)
) -> list[Renewal]:
    """Negotiations whose promotional period is about to lapse.

    A negotiated rate is temporary. The month before it expires is when calling
    again is worth something, and after it expires the customer is simply
    paying more without having been told.
    """
    today = date.today()
    horizon = today + timedelta(days=within_days)

    renewals: list[Renewal] = []
    # Scoped to the caller. Unscoped, this listed other people's
    # providers and renewal dates to anyone signed in.
    for session in await list_sessions(user_id):
        # A seeded example carries a contract end date so the bill looks real,
        # which meant it surfaced here as a genuine renewal and invited a call
        # to a company about a bill that does not exist.
        if session.is_sample:
            continue
        if session.bill is None or not session.bill.contract_end_date:
            continue
        end = _parse_day(session.bill.contract_end_date)
        if end is None or end > horizon:
            continue

        renewals.append(
            Renewal(
                task_id=session.task_id,
                provider=session.provider,
                contract_end_date=end.isoformat(),
                days_remaining=(end - today).days,
                current_rate=session.bill.current_rate,
                negotiated_rate=session.new_rate,
            )
        )

    # Soonest first - including any already past, which matter most.
    renewals.sort(key=lambda r: r.days_remaining)
    return renewals
