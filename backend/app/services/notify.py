"""Reach the customer when the agent can't finish the call alone.

escalate_to_human used to set a flag on a session nobody was watching, which is
not an escalation - it is a note. A call that has hit a wall is time-sensitive:
the representative is on the line now, and a customer who learns about it
tomorrow has lost the call.

Three channels, in the order they are worth trying:

  SMS       through the Twilio number that already places the calls. Nothing
            new to sign up for, no session window, no template approval - and
            an escalation fires exactly when somebody is not looking at their
            phone, which is when the other two are least reliable.
  WhatsApp  through Twilio as well. Free on the sandbox, but the sandbox only
            accepts free-form messages within 24 hours of the recipient's last
            inbound message, so it is a good second channel and a poor only one.
  email     through Resend. SendGrid's permanent free tier was retired in May
            2025 - new accounts get sixty days and then a $19.95 floor - and
            paying that to email one person about their own call is not a
            trade worth making.

All three are optional and all three fail soft: a notification that cannot be
delivered must never take down a live phone call, so every failure here is
logged and swallowed.

Where a person is reached comes from *their own profile*, not from the
deployment's environment. Orion is multi-tenant: a single ESCALATION_EMAIL_TO
would page one address about every customer's call, and tell that address about
negotiations belonging to strangers. The environment values remain only as a
fallback for a single-user or local deployment where no profile exists.
"""

import logging
from typing import NamedTuple

import httpx

from app.config import settings
from app.services import supabase_store
from app.models import NegotiationSession, UserProfile

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TWILIO_MESSAGES = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


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


class Recipients(NamedTuple):
    sms: str | None
    whatsapp: str | None
    email: str | None


async def _recipients(session: NegotiationSession) -> Recipients:
    """Where this customer is reached, falling back to the deployment's own
    addresses only when the session has no owner or no profile."""
    profile: UserProfile | None = None
    if session.user_id:
        try:
            profile = await supabase_store.get_profile(session.user_id)
        except Exception as exc:  # noqa: BLE001 - never break a live call
            logger.warning("Could not load the profile for %s: %s", session.user_id, exc)

    whatsapp = (profile.escalation_whatsapp if profile else None) or settings.escalation_whatsapp_to
    # Somebody who gave a WhatsApp number and no separate mobile almost
    # certainly meant the same handset. Their own phone number is the next
    # best guess, since a rep would ring it.
    sms = (
        (profile.escalation_sms if profile else None)
        or (profile.phone if profile else None)
        or whatsapp
        or settings.escalation_sms_to
    )
    email = (profile.escalation_email if profile else None) or (
        (profile.email if profile else None) or settings.escalation_email_to
    )
    return Recipients(sms or None, whatsapp or None, email or None)


async def _send_sms(body: str, to: str | None) -> bool:
    """The Twilio number that placed the call sends the alert about it.

    No second account, no verification, and no 24-hour window - which is the
    one that matters, because an escalation happens when the customer is not
    already in a conversation with us.
    """
    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_phone_number
        and to
    ):
        return False

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            TWILIO_MESSAGES.format(sid=settings.twilio_account_sid),
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={
                "From": settings.twilio_phone_number,
                "To": to,
                # An SMS is charged per 160 characters, and the whole message is
                # a summary of something the customer can open in the app.
                "Body": body[:640],
            },
        )
        res.raise_for_status()
    return True


async def _send_whatsapp(body: str, to: str | None) -> bool:
    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_whatsapp_from
        and to
    ):
        return False

    # The sandbox number arrives already prefixed; a production sender may not.
    sender = settings.twilio_whatsapp_from
    if not sender.startswith("whatsapp:"):
        sender = f"whatsapp:{sender}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            TWILIO_MESSAGES.format(sid=settings.twilio_account_sid),
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={
                # Twilio requires the whatsapp: prefix on both ends; without it
                # the message is attempted as SMS and fails on a WhatsApp number.
                "From": sender,
                "To": to if to.startswith("whatsapp:") else f"whatsapp:{to}",
                "Body": body,
            },
        )
        res.raise_for_status()
    return True


async def _send_email(subject: str, body: str, to: str | None) -> bool:
    """Resend, not SendGrid.

    Resend's free tier is 3,000 emails a month and stays free; SendGrid's
    hundred-a-day tier was retired in May 2025, so the same job now starts at
    $19.95 a month once a sixty-day trial ends.

    `escalation_email_from` must be an address on a domain verified with
    Resend, or the API refuses it - onboarding@resend.dev works without a
    domain and is the right default for a deployment that has not verified one.
    """
    if not (settings.resend_api_key and to):
        return False

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.escalation_email_from or "Orion <onboarding@resend.dev>",
                "to": [to],
                "subject": subject,
                "text": body,
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

    to = await _recipients(session)
    for channel, send in (
        # SMS first: it is the one with no session window, so it is the one
        # most likely to arrive when somebody is not already talking to us.
        ("SMS", _send_sms(body, to.sms)),
        ("WhatsApp", _send_whatsapp(body, to.whatsapp)),
        ("email", _send_email(subject, body, to.email)),
    ):
        try:
            if await send:
                delivered.append(channel)
        except Exception as exc:  # noqa: BLE001 - never break a live call
            logger.warning("Escalation over %s failed for %s: %s", channel, session.task_id, exc)

    if not delivered:
        logger.info("No escalation channel configured for %s", session.task_id)
    return delivered
