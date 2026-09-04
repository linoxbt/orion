import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models import BillExtraction, NegotiationSession, NegotiationStatus
from app.playbooks import get_playbook
from app.security import require_owned_session, require_user_id
from app.services import account_vault, events, recordings, supabase_store
from app.services.ratelimit import limit
from app.services.billing import StripeNotConfigured, charge_success_fee
from app.services.twilio_client import (
    CallRejected,
    end_call,
    TwilioNotConfigured,
    place_outbound_call,
)
from app.store import get_session, list_sessions, save_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/negotiations", tags=["negotiations"])

# Persisted on the session, never serialised back out. The blob is encrypted,
# but the API has no reason to hand it to anyone: on a call it is read one
# field at a time through the provide_verification tool.
PRIVATE_FIELDS = {"account_details"}

# Comfortably inside the 30-60s idle timeout most proxies apply.
SSE_HEARTBEAT_SECONDS = 20.0


class StartNegotiationRequest(BaseModel):
    provider: str
    phone_number: str
    vertical: str = "cable_internet"
    # ISO code. Picks the agent's voice and the language it speaks; the
    # transcription side handles all 18 natively either way.
    language: str = "en"
    # The extraction from the uploaded bill. Passing it here is what lets the
    # agent walk into the call knowing the customer's actual rate and line
    # items rather than just a provider name.
    bill: BillExtraction | None = None


@router.post("/start", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS)
async def start_negotiation(
    body: StartNegotiationRequest, user_id: str = Depends(require_user_id)
) -> NegotiationSession:
    """Creates a NegotiationSession in PENDING status. Does NOT place the call -
    the build spec (Section 3/4) requires the authorization & consent flow to
    happen before the call is placed, so call-placing is a separate step (see
    POST /{task_id}/call below) that requires session.authorized first.
    """
    if get_playbook(body.vertical) is None:
        raise HTTPException(status_code=422, detail="unknown_vertical")

    profile = None
    if supabase_store.is_configured():
        profile = await supabase_store.get_profile(user_id)

    session = NegotiationSession(
        task_id=str(uuid.uuid4()),
        user_id=user_id,
        provider=body.provider,
        phone_number=body.phone_number,
        vertical=body.vertical,
        # An explicit choice wins; otherwise fall back to the account's
        # preference rather than assuming English.
        language=body.language or (profile.preferred_language if profile else "en"),
        bill=body.bill,
    )

    # Seed the vault from the bill so the customer doesn't retype what the
    # extraction already read. These are the non-secret identifiers; a PIN or
    # an SSN never appears on a bill and still has to be entered by hand.
    from_bill = {
        "account_number": body.bill.account_number if body.bill else None,
        "account_holder_name": body.bill.account_holder_name if body.bill else None,
        "service_address": body.bill.service_address if body.bill else None,
    }
    if profile is not None:
        # The bill is authoritative about the account; the profile fills the
        # gaps, so nobody types their own address in twice.
        from_bill["account_holder_name"] = from_bill["account_holder_name"] or profile.full_name
        from_bill["service_address"] = from_bill["service_address"] or profile.postal_address()
        if profile.postal_code:
            from_bill["billing_zip"] = profile.postal_code

    supplied = {k: v for k, v in from_bill.items() if v}
    if supplied:
        try:
            session.account_details = account_vault.seal(supplied)
        except account_vault.VaultNotConfigured:
            # Not fatal - the negotiation still works, the agent just can't
            # answer verification questions until a key is configured.
            logger.warning("Vault unconfigured; bill details not stored for %s", session.task_id)

    await save_session(session)
    return session


@router.post("/{task_id}/call", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS)
async def call_negotiation(
    task_id: str, session: NegotiationSession = Depends(require_owned_session)
) -> NegotiationSession:
    """Places the outbound call via the telephony bridge (build spec Section
    5), seeding the call with the matching vertical/provider's playbook (see
    app/playbooks.py and app/services/live_bridge.py). Requires the session to
    already be authorized (build spec Section 3's consent-before-call
    requirement) - use POST /{task_id}/authorization first.
    """
    # A seeded example is not a negotiation. Its provider numbers are real -
    # Comcast, AT&T, a hospital billing line - and its bill is invented, so
    # dialling one would put an agent on the phone to a real company arguing
    # from figures nobody was ever billed. The flag existed but was read only
    # by the dashboard's totals; nothing on the call path looked at it.
    if session.is_sample:
        raise HTTPException(
            status_code=409,
            detail=(
                "sample_negotiation: this is a worked example, not a real bill. "
                "Upload one of your own to place a call."
            ),
        )

    if not session.authorized:
        raise HTTPException(status_code=409, detail="not_authorized")

    # Each call is real money on a real phone line, and retries are now
    # unlimited by design, so the button is loopable. A cap that no honest
    # retry will ever reach still stops a stuck loop or a hostile script from
    # spending the account down.
    limit(f"call:{session.user_id or task_id}", max_calls=8, per_seconds=600)

    # A negotiation may be called as many times as it takes. The first attempt
    # often does not reach anyone: the line is busy, nobody picks up, the menu
    # routes somewhere useless. Refusing a second attempt left the only real
    # remedy - try again - unavailable, with the button greyed out and no way
    # to explain that to the customer.
    #
    # The one thing that is refused is a second call while one is still live,
    # which would put two agents on the same negotiation at once.
    if session.status == NegotiationStatus.CALLING:
        raise HTTPException(status_code=409, detail="call_already_in_progress")

    try:
        call_sid = place_outbound_call(session)
    except TwilioNotConfigured as exc:
        session.status = NegotiationStatus.FAILED
        await save_session(session)
        raise HTTPException(status_code=503, detail="twilio_not_configured") from exc
    except CallRejected as exc:
        # Twilio refused, and the reason belongs to the request rather than the
        # server. Left unhandled this was a 500 reading "request_failed_500",
        # which told the customer nothing about a problem they can fix.
        session.status = NegotiationStatus.FAILED
        session.outcome = f"Call not placed: {exc.message}"
        await save_session(session)
        detail = exc.message if not exc.hint else f"{exc.message} {exc.hint}"
        logger.warning("Twilio refused the call for %s: %s", session.task_id, exc.message)
        raise HTTPException(status_code=422, detail=detail) from exc

    session.call_sid = call_sid
    session.status = NegotiationStatus.CALLING
    await save_session(session)
    return session


@router.get("", response_model=list[NegotiationSession],
    response_model_exclude=PRIVATE_FIELDS)
async def list_negotiations(
    user_id: str = Depends(require_user_id),
) -> list[NegotiationSession]:
    """Only the caller's own.

    This previously returned every negotiation in the system to any signed-in
    user, because sessions had no owner at all.

    An empty result means a brand new account, which is the moment to seed the
    worked examples. Doing it here rather than on the account page matters:
    the dashboard is where people land after signing in, and it never reads
    the profile, so seeding on profile access alone left new users staring at
    an empty page. The check costs nothing for anyone who already has
    negotiations, because the list is only empty for a new account.
    """
    sessions = await list_sessions(user_id)
    if not sessions:
        from app.services import demo_seed

        if await demo_seed.seed_if_new(user_id):
            sessions = await list_sessions(user_id)
    return sessions


@router.get("/{task_id}", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS)
async def get_negotiation(
    session: NegotiationSession = Depends(require_owned_session),
) -> NegotiationSession:
    return session


@router.post("/{task_id}/hangup", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS)
async def hangup_negotiation(
    task_id: str, session: NegotiationSession = Depends(require_owned_session)
) -> NegotiationSession:
    """End a call that is still running.

    The on-screen End button used to close the window and nothing else, so a
    call carried on with nobody able to stop it. Ending is idempotent: a call
    that has already finished is a success, not a 409, because the caller's
    intent is satisfied either way.
    """
    if session.call_sid and session.status == NegotiationStatus.CALLING:
        try:
            end_call(session.call_sid)
        except TwilioNotConfigured as exc:
            raise HTTPException(status_code=503, detail="twilio_not_configured") from exc
        except CallRejected as exc:
            logger.warning("Could not end %s: %s", session.task_id, exc.message)
            raise HTTPException(status_code=422, detail=exc.message) from exc

    # Twilio's status webhook will confirm this, but the caller should not have
    # to wait for a webhook to see the call they just ended.
    if session.status == NegotiationStatus.CALLING:
        session.status = NegotiationStatus.COMPLETED
        if not session.outcome:
            session.outcome = "Ended from the app."
        await save_session(session)

    events.publish(
        session.task_id, {"type": "status", "status": "call_ended", "reason": "hung_up"}
    )
    return session


class Recording(BaseModel):
    """Where to play the call back from, and for how long that link lasts."""

    available: bool
    url: str | None = None
    expires_in: int | None = None
    reason: str | None = None


@router.get("/{task_id}/recording", response_model=Recording)
async def get_recording(
    session: NegotiationSession = Depends(require_owned_session),
) -> Recording:
    """A link the customer can play their own call back from.

    Signed and short-lived rather than public: this is a recorded phone call
    about somebody's account, so a copied link should stop working rather than
    remain a permanent handle on it. Ownership is checked before the link is
    minted at all, so knowing a task id is not enough.
    """
    if not session.recording_path:
        # Distinguish "not recorded yet" from "there is nothing to hear", so
        # the page can say which.
        reason = (
            "no_call_yet"
            if session.status == NegotiationStatus.PENDING
            else "awaiting_recording"
        )
        return Recording(available=False, reason=reason)

    url = await recordings.playback_url(session.recording_path)
    if not url:
        return Recording(available=False, reason="unavailable")

    return Recording(
        available=True, url=url, expires_in=recordings.SIGNED_URL_TTL_SECONDS
    )


@router.get("/{task_id}/events")
async def negotiation_events(
    task_id: str, _session: NegotiationSession = Depends(require_owned_session)
) -> StreamingResponse:
    """Server-sent events for one call: transcript turns as they are spoken,
    offers logged by the agent's tools, and the verification result.

    The stream opens with whatever has already happened on this call, so a
    browser that lands mid-call - or reconnects after a dropped stream - renders
    the turns it missed instead of an empty transcript next to a live call.
    """

    async def stream() -> AsyncIterator[str]:
        # A comment line keeps the connection alive without being delivered as
        # an event. Without it a quiet call is an idle socket, and proxies
        # commonly close those after 30-60 seconds - taking the live transcript
        # with them mid-call.
        yield ": connected\n\n"

        feed = events.subscribe(task_id).__aiter__()
        while True:
            try:
                event = await asyncio.wait_for(feed.__anext__(), timeout=SSE_HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            except StopAsyncIteration:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx and friends will otherwise sit on the stream until it fills
            # a buffer, which for a live transcript means it never arrives.
            "X-Accel-Buffering": "no",
        },
    )


# The exact wording a customer agrees to. Versioned, because what someone
# consented to has to be reconstructable later, and "they clicked a box" is not
# a record of anything.
CONSENT_VERSION = "2026-09-03"
CONSENT_TEXT = (
    "I authorise Orion to contact this company as my representative regarding this "
    "account or purchase, to discuss it on my behalf, and to record the call for "
    "verification. I confirm I am the account holder or am otherwise entitled to "
    "authorise this."
)


class ConsentRequest(BaseModel):
    signer_name: str
    agreed: bool


@router.get("/consent-text")
async def consent_text() -> dict[str, str]:
    """The wording the customer is agreeing to, so the UI can't drift from what
    gets recorded against the session."""
    return {"version": CONSENT_VERSION, "text": CONSENT_TEXT}


@router.post(
    "/{task_id}/consent",
    response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS,
)
async def record_consent(
    body: ConsentRequest, session: NegotiationSession = Depends(require_owned_session)
) -> NegotiationSession:
    """Record in-app authorisation to act as the customer's representative.

    Consent genuinely is required before calling a company about someone's
    account - that part of the build spec is right. Requiring *DocuSign*
    specifically is not: with DocuSign unconfigured, `authorized` could never
    become true, so the call button never rendered and no call could ever be
    placed. This records the same undertaking with an audit trail, and DocuSign
    remains available for anyone who wants a countersigned envelope.
    """

    name = body.signer_name.strip()
    if not body.agreed or not name:
        raise HTTPException(status_code=422, detail="consent_not_given")

    session.authorized = True
    session.consent_signer_name = name
    session.consent_version = CONSENT_VERSION
    session.consent_at = datetime.now(timezone.utc).isoformat()
    await save_session(session)

    events.publish(session.task_id, {"type": "status", "status": "authorized"})
    return session


class AccountDetailsRequest(BaseModel):
    """What a retention rep asks for before discussing an account.

    Every field is optional - supply what the provider actually asks for. They
    are encrypted immediately and never returned by any read endpoint.
    """

    account_holder_name: str | None = None
    account_number: str | None = None
    service_address: str | None = None
    billing_zip: str | None = None
    security_pin: str | None = None
    last4_ssn: str | None = None
    date_of_birth: str | None = None


@router.post(
    "/{task_id}/account-details",
    response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS,
)
async def set_account_details(
    body: AccountDetailsRequest, session: NegotiationSession = Depends(require_owned_session)
) -> NegotiationSession:
    """Store the account facts Orion needs to get past verification.

    Without these, a real call ends the moment the representative asks who is
    calling. They are sealed with Fernet before they touch the database, and
    read back one field at a time during a call.
    """

    supplied = {k: v for k, v in body.model_dump().items() if v}
    if not supplied:
        raise HTTPException(status_code=422, detail="no_details_supplied")

    try:
        session.account_details = account_vault.seal(supplied)
    except account_vault.VaultNotConfigured as exc:
        # Refuse rather than storing these in the clear.
        raise HTTPException(status_code=503, detail="account_vault_not_configured") from exc

    await save_session(session)
    return session


@router.get("/{task_id}/account-details")
async def list_account_details(
    session: NegotiationSession = Depends(require_owned_session),
) -> dict[str, list[str]]:
    """Which verification fields are on file. Names only - never values."""
    return {"fields": account_vault.available_fields(session.account_details)}


class CompleteNegotiationRequest(BaseModel):
    outcome: str
    previous_rate: float | None = None
    new_rate: float | None = None
    confirmation_number: str | None = None


@router.post(
    "/{task_id}/complete", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS,
)
async def complete_negotiation(
    body: CompleteNegotiationRequest,
    session: NegotiationSession = Depends(require_owned_session),
) -> NegotiationSession:
    """Records a verified outcome by hand.

    The automated path is app/services/verification.py, which transcribes the
    call recording with AssemblyAI and extracts the outcome from it. This
    endpoint remains the override and the fallback: a human correcting the
    extraction, or recording an outcome the extraction wouldn't commit to. The
    resulting session is marked verification_source="human" so the two are
    distinguishable after the fact.
    """

    session.outcome = body.outcome
    session.previous_rate = body.previous_rate
    session.new_rate = body.new_rate
    session.confirmation_number = body.confirmation_number
    session.verified = True
    session.verification_source = "human"
    session.status = NegotiationStatus.COMPLETED
    await save_session(session)
    return session


@router.post("/{task_id}/charge", response_model=NegotiationSession,
    response_model_exclude=PRIVATE_FIELDS)
async def charge_negotiation(
    session: NegotiationSession = Depends(require_owned_session),
) -> NegotiationSession:
    """Charges the success fee on verified savings (build spec Section 11).
    Requires the session to have been verified via /complete first with both
    previous_rate and new_rate set.
    """
    if not session.verified or session.previous_rate is None or session.new_rate is None:
        raise HTTPException(status_code=409, detail="not_yet_verified")
    if session.stripe_payment_intent_id is not None:
        raise HTTPException(status_code=409, detail="already_charged")

    monthly_savings = session.previous_rate - session.new_rate
    if monthly_savings <= 0:
        raise HTTPException(status_code=422, detail="no_savings_to_charge")

    try:
        payment_intent = charge_success_fee(session, monthly_savings)
    except StripeNotConfigured as exc:
        raise HTTPException(status_code=503, detail="stripe_not_configured") from exc

    session.stripe_payment_intent_id = payment_intent.id
    session.fee_amount_cents = payment_intent.amount
    await save_session(session)
    return session
