"""Five worked examples on a new account, so the dashboard is not an empty page.

A brand new account has nothing in it, which makes the product impossible to
show and hard to understand: the dashboard, the receipt and the renewal
reminder all only mean something once there is a negotiation to look at.

Every row here is flagged `is_sample`. That matters more than it might seem.
An unmarked example carrying a plausible saving would be added into the totals
and read as money the customer actually kept, which is a lie the interface
would be telling on our behalf. The UI badges them and excludes them from
every sum, and the moment a real negotiation exists they can be ignored.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.models import BillExtraction, NegotiationSession, NegotiationStatus, Offer

logger = logging.getLogger(__name__)


def build_samples(user_id: str) -> list[NegotiationSession]:
    """One of each state a negotiation can be in, so every part of the
    interface has something to render."""
    soon = (datetime.now(timezone.utc) + timedelta(days=21)).date().isoformat()

    return [
        # A win, verified, with a receipt worth looking at.
        NegotiationSession(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            is_sample=True,
            provider="Comcast",
            phone_number="+18009346489",
            vertical="cable_internet",
            status=NegotiationStatus.COMPLETED,
            outcome="Moved to the 12-month loyalty promotion after retention was reached.",
            confirmation_number="CMC-8841207",
            previous_rate=89.99,
            new_rate=54.99,
            verified=True,
            verification_source="call recording",
            offers=[
                Offer(monthly_rate=79.99, description="First offer, declined as too thin"),
                Offer(monthly_rate=54.99, description="Retention's 12-month promotional rate"),
            ],
            bill=BillExtraction(
                provider="Comcast",
                current_rate=89.99,
                plan_details="Performance Pro internet, 300 Mbps",
                billing_period="Monthly",
                contract_end_date=soon,
                objective_summary="Match the advertised new-customer rate without a contract extension.",
            ),
        ),
        # A win that is still awaiting its recording, so nothing is claimed yet.
        NegotiationSession(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            is_sample=True,
            provider="Verizon",
            phone_number="+18009220204",
            vertical="cell_phone",
            status=NegotiationStatus.COMPLETED,
            outcome="Agent applied a loyalty credit; awaiting the recording before it counts.",
            previous_rate=75.00,
            new_rate=60.00,
            verified=False,
            offers=[Offer(monthly_rate=60.00, description="Loyalty credit, 6 months")],
            bill=BillExtraction(
                provider="Verizon",
                current_rate=75.00,
                plan_details="Unlimited Plus, single line",
                billing_period="Monthly",
            ),
        ),
        # Live, so the call screen and the transcript feed have a subject.
        NegotiationSession(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            is_sample=True,
            provider="Movistar",
            phone_number="+34911111111",
            vertical="cable_internet",
            language="es",
            status=NegotiationStatus.CALLING,
            bill=BillExtraction(
                provider="Movistar",
                current_rate=48.50,
                plan_details="Fusion fibra 600 Mb",
                billing_period="Mensual",
                objective_summary="Renegociar la tarifa antes de que expire la promocion.",
            ),
        ),
        # Ready to run, which is what a new negotiation looks like.
        NegotiationSession(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            is_sample=True,
            provider="Anthem Blue Cross",
            phone_number="+18008888888",
            vertical="medical",
            status=NegotiationStatus.PENDING,
            bill=BillExtraction(
                provider="Anthem Blue Cross",
                current_rate=1240.00,
                plan_details="Outpatient procedure, itemisation requested",
                objective_summary="Request itemisation, then financial hardship review.",
            ),
        ),
        # A call that hit a wall, so the escalation path is visible too.
        NegotiationSession(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            is_sample=True,
            provider="AT&T",
            phone_number="+18003310500",
            vertical="cell_phone",
            status=NegotiationStatus.FAILED,
            outcome="Ended at verification: the account PIN on file did not match.",
            escalated=True,
            escalation_reason="Representative asked for a PIN Orion had not been given.",
            bill=BillExtraction(provider="AT&T", current_rate=64.99, plan_details="Unlimited Starter"),
        ),
    ]


async def seed_if_new(user_id: str) -> int:
    """Seed a brand new account, and never a second time.

    Guarded on the account genuinely having nothing rather than on a flag, so
    a failure partway through cannot leave someone permanently unseeded, and a
    returning customer never has examples appear among real negotiations.
    """
    from app.store import list_sessions, save_session

    try:
        if await list_sessions(user_id, limit=1):
            return 0
        samples = build_samples(user_id)
        for sample in samples:
            await save_session(sample)
        logger.info("Seeded %s example negotiations for %s", len(samples), user_id)
        return len(samples)
    except Exception as exc:  # noqa: BLE001 - a demo row must never block sign-in
        logger.warning("Could not seed examples for %s: %s", user_id, exc)
        return 0
