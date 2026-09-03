"""Reach the customer when the agent can't finish the call alone.

escalate_to_human used to set a flag on a session nobody was watching, which is
not an escalation - it is a note. A call that has hit a wall is time-sensitive:
the representative is on the line now, and a customer who learns about it
tomorrow has lost the call.

WhatsApp goes through Twilio, email through SendGrid. Both are optional and
both fail soft: a notification that cannot be delivered must never take down a
live phone call, so every failure here is logged and swallowed.

Where a person is reached comes from *their own profile*, not from the
deployment's environment. Orion is multi-tenant: a single ESCALATION_EMAIL_TO
would page one address about every customer's call, and tell that address about
negotiations belonging to strangers. The environment values remain only as a
fallback for a single-user or local deployment where no profile exists.
"""

import logging

import httpx

from app.config import settings
from app.services import supabase_store
from app.models import NegotiationSession, UserProfile

logger = logging.getLogger(__name__)

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def _message(session: NegotiationSession, reason: str) -> str:
    provider = session.provider
    lines = [
        f"Orion needs you on the call with {provider}.",
        "",
        f"Reason: {reason}" if reason else "The agent could not continue alone.",
    ]
    if session.bill and session.bill.objective_summary:
        lines += ["", f"What it was asking for: {session.bill.objective_summary}"]
    if session.offers:
        best = min(
            (o for o in session.offers if o.monthly_rate is not None),
            key=lambda o: o.monthly_rate,
            default=None,
        )
        if best is not None:
            lines += ["", f"Best offer so far: {best.monthly_rate} - {best.description}"]
    if settings.public_app_url:
        lines += ["", f"{settings.public_app_url}/negotiate/{session.task_id}"]
    return "\n".join(lines)


async def _recipients(session: NegotiationSession) -> tuple[str | None, str | None]:
    """This customer's WhatsApp number and email, falling back to the
    deployment's own only when the session has no owner or no profile."""
    profile: UserProfile | None = None
    if session.user_id:
        try:
            profile = await supabase_store.get_profile(session.user_id)
        except Exception as exc:  # noqa: BLE001 - never break a live call
            logger.warning("Could not load the profile for %s: %s", session.user_id, exc)

    whatsapp = (profile.escalation_whatsapp if profile else None) or settings.escalation_whatsapp_to
    email = (profile.escalation_email if profile else None) or (
        (profile.email if profile else None) or settings.escalation_email_to
    )
    return whatsapp or None, email or None


async def _send_whatsapp(body: str, to: str | None) -> bool:
    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_whatsapp_from
        and to
    ):
        return False

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={
                # Twilio requires the whatsapp: prefix on both ends; without it
                # the message is attempted as SMS and fails on a WhatsApp number.
                "From": f"whatsapp:{settings.twilio_whatsapp_from}",
                "To": f"whatsapp:{to}",
                "Body": body,
            },
        )
        res.raise_for_status()
    return True


async def _send_email(subject: str, body: str, to: str | None) -> bool:
    if not (settings.sendgrid_api_key and to):
        return False

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            SENDGRID_URL,
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.escalation_email_from or to},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            },
        )
        res.raise_for_status()
    return True


async def escalate(session: NegotiationSession, reason: str) -> list[str]:
    """Tell the customer their call needs them. Returns the channels that
    actually delivered, so the agent can say so on the line."""
    body = _message(session, reason)
    subject = f"Orion needs you - {session.provider}"
    delivered: list[str] = []

    whatsapp_to, email_to = await _recipients(session)
    for channel, send in (
        ("WhatsApp", _send_whatsapp(body, whatsapp_to)),
        ("email", _send_email(subject, body, email_to)),
    ):
        try:
            if await send:
                delivered.append(channel)
        except Exception as exc:  # noqa: BLE001 - never break a live call
            logger.warning("Escalation over %s failed for %s: %s", channel, session.task_id, exc)

    if not delivered:
        logger.info("No escalation channel configured for %s", session.task_id)
    return delivered
