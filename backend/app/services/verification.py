"""Post-call verification: prove what was actually agreed on the call.

The build spec (Section 9) calls this the hard part, and shipped as a human
review queue - somebody listened back to the call and typed the outcome into
POST /api/negotiations/{task_id}/complete. This replaces that with an
AssemblyAI pre-recorded pass:

    Twilio recording -> /v2/upload -> /v2/transcript -> webhook
                     -> LLM Gateway extraction -> the same complete() path

Twilio's media URLs sit behind HTTP basic auth, which AssemblyAI cannot use,
so the recording is downloaded here and re-uploaded rather than handed over as
a URL.

Money amounts and number sequences are deliberately NOT redacted: the agreed
rate and the confirmation number are the entire point of the exercise. Account
numbers, card details and personal identifiers are.
"""

import logging
from typing import Any

import httpx

from app.config import settings
from app.models import NegotiationSession, NegotiationStatus
from app.services import events
from app.services import recordings
from app.services.assemblyai import REST_BASE, llm_gateway_json, rest_headers
from app.store import save_session

logger = logging.getLogger(__name__)

# Verified against the policy list in AssemblyAI's PII redaction docs.
# money_amount and number_sequence are excluded on purpose - redacting them
# would erase the negotiated rate and the confirmation number.
REDACT_POLICIES = [
    "account_number",
    "banking_information",
    "credit_card_number",
    "credit_card_cvv",
    "credit_card_expiration",
    "drivers_license",
    "email_address",
    "passport_number",
    "person_name",
    "phone_number",
    "us_social_security_number",
]

# How short a recording has to be before there is plainly no conversation in
# it. A greeting and a hang-up fit comfortably inside this.
MIN_CONVERSATION_SECONDS = 8

# Outcomes that are established fact rather than interpretation. Once one of
# these is set, the transcript read-back must not replace it.
_FACTUAL_OUTCOMES = {"not_answered", "too_short"}

_EXTRACTION_PROMPT = """You are reading a transcript of a recording of an outbound phone call. \
An AI agent was calling a company to negotiate a customer's bill. The call may or may not have \
reached a real person: it may be silence, a voicemail greeting, a hold loop, an automated menu, \
or a few seconds of nothing.

Decide first whether an actual conversation with a representative took place. If it did not, say \
so plainly - "The call was not answered", "The call reached voicemail", "Nobody spoke" - set \
"agreed" to false, and leave every rate and number null. Never characterise what a representative \
said, or failed to say, when no representative spoke. Describing an unanswered call as one where \
someone "did not make a clear statement" is wrong: it invents a person.

Return ONLY a JSON object with these keys:
  "agreed": boolean - did the representative actually commit to a change?
  "outcome": string - one sentence describing what was agreed, or why nothing was.
  "previous_rate": number or null - the monthly rate before the change, in USD.
  "new_rate": number or null - the agreed monthly rate after the change, in USD.
  "confirmation_number": string or null - the confirmation or reference number, if one was read out.

Rules: only report a rate or confirmation number the representative actually stated. \
If the call ended without a firm commitment, "agreed" is false and the rates are null. \
Never infer or invent a confirmation number. Personal identifiers appear as [BRACKETED_LABELS] \
because they were redacted - that is expected, ignore them."""


def _transcript_webhook_url(task_id: str) -> str:
    return f"{settings.base_url}/telephony/transcript?taskId={task_id}"


async def start_verification(session: NegotiationSession) -> None:
    """Called when the call ends. The recording is not ready yet - Twilio posts
    to /telephony/recording once it is, which is what actually kicks off
    ingest_recording. This just moves the session out of CALLING so the
    dashboard stops showing a live call that has hung up.
    """
    if session.status == NegotiationStatus.CALLING:
        session.status = NegotiationStatus.PENDING
        await save_session(session)
    events.publish(session.task_id, {"type": "status", "status": "awaiting_recording"})


async def ingest_recording(
    session: NegotiationSession, recording_url: str, duration_seconds: int = 0
) -> str | None:
    """Download the Twilio recording, upload it, and submit it for transcription.

    Returns the transcript id, or None if AssemblyAI or Twilio isn't configured.
    """
    session.recording_url = recording_url
    await save_session(session)

    # Nothing was said, so there is nothing to read back.
    #
    # A call nobody answered still leaves a recording of a second or two, and
    # feeding that to a model which has been told it is reading a negotiation
    # is exactly how Orion came to report that "the representative didn't make
    # a clear statement" about a call that was never picked up. The factual
    # outcome the status webhook already wrote is the true one; keep it.
    if not session.answered_at:
        logger.info("Skipping verification for %s: never answered", session.task_id)
        session.outcome = session.outcome or "The call was not answered."
        session.verification_source = "not_answered"
        await save_session(session)
        return None

    if duration_seconds and duration_seconds < MIN_CONVERSATION_SECONDS:
        logger.info(
            "Skipping verification for %s: only %ss of audio",
            session.task_id,
            duration_seconds,
        )
        session.outcome = session.outcome or (
            f"The call ended after {duration_seconds} seconds, before anything was agreed."
        )
        session.verification_source = "too_short"
        await save_session(session)
        return None

    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Twilio serves the raw media from the recording URL with a format suffix.
        audio = await client.get(f"{recording_url}.wav", auth=auth)
        audio.raise_for_status()

        # Keep our own copy before anything else touches it. Twilio holds the
        # original behind account credentials the browser must never see, and
        # deletes it when an account lapses - so the customer's ability to hear
        # their own call should not depend on our telephony account still
        # existing. Failing to store must not stop the verification that
        # follows, which is the part a saving depends on.
        try:
            stored = await recordings.store(session.user_id, session.task_id, audio.content)
            if stored:
                session.recording_path = stored
                await save_session(session)
        except Exception as exc:  # noqa: BLE001 - never block verification
            logger.warning("Could not archive the recording for %s: %s", session.task_id, exc)

        # /v2/upload takes raw binary - NOT multipart.
        upload = await client.post(
            f"{REST_BASE}/v2/upload", headers=rest_headers(), content=audio.content
        )
        upload.raise_for_status()
        upload_url = upload.json()["upload_url"]

        submit = await client.post(
            f"{REST_BASE}/v2/transcript",
            headers={**rest_headers(), "content-type": "application/json"},
            json={
                "audio_url": upload_url,
                # Ordered availability fallback, plural array - pre-recorded only.
                "speech_models": ["universal-3-5-pro", "universal-2"],
                "speaker_labels": True,
                "redact_pii": True,
                "redact_pii_policies": REDACT_POLICIES,
                # Keeps the transcript readable for the extraction pass below.
                "redact_pii_sub": "entity_name",
                "webhook_url": _transcript_webhook_url(session.task_id),
                # AssemblyAI can't sign like Twilio does, so the callback
                # authenticates with the same shared admin key the rest of the
                # privileged routes use.
                "webhook_auth_header_name": "X-Orion-Admin-Key",
                "webhook_auth_header_value": settings.admin_api_key,
            },
        )
        submit.raise_for_status()
        transcript_id = submit.json()["id"]

    session.transcript_id = transcript_id
    await save_session(session)
    events.publish(session.task_id, {"type": "status", "status": "transcribing"})
    logger.info("Submitted transcript %s for task %s", transcript_id, session.task_id)
    return transcript_id


async def fetch_transcript(transcript_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(f"{REST_BASE}/v2/transcript/{transcript_id}", headers=rest_headers())
        res.raise_for_status()
    return res.json()


def _dialogue(transcript: dict[str, Any]) -> str:
    """Speaker-labelled dialogue, falling back to the flat transcript text."""
    utterances = transcript.get("utterances") or []
    if not utterances:
        return transcript.get("text") or ""
    return "\n".join(
        f"Speaker {utterance.get('speaker', '?')}: {utterance.get('text', '')}"
        for utterance in utterances
    )


async def apply_transcript(session: NegotiationSession, transcript_id: str) -> NegotiationSession:
    """Extract the outcome from a finished transcript and record it on the session.

    Anything the extraction can't establish is left for a human: an unparseable
    reply, or a call with no firm commitment, leaves verified False rather than
    writing a guess into a record that Stripe bills against.
    """
    transcript = await fetch_transcript(transcript_id)
    if transcript.get("status") == "error":
        logger.error("Transcript %s failed: %s", transcript_id, transcript.get("error"))
        events.publish(session.task_id, {"type": "error", "message": "transcription_failed"})
        return session

    dialogue = _dialogue(transcript)
    extracted = await llm_gateway_json(
        [
            {"role": "system", "content": _EXTRACTION_PROMPT},
            {"role": "user", "content": dialogue},
        ],
        max_tokens=600,
    )

    if extracted is None:
        session.outcome = session.outcome or "Transcript could not be parsed automatically."
        session.verification_source = "needs_human_review"
        await save_session(session)
        events.publish(session.task_id, {"type": "status", "status": "needs_human_review"})
        return session

    # A fact never loses to a guess. When the call ended in a way that already
    # explains itself - nobody answered, the line was busy, it failed - that
    # outcome stands, and the transcript read-back may not paper over it.
    if session.verification_source not in _FACTUAL_OUTCOMES:
        session.outcome = extracted.get("outcome") or session.outcome
    # Tool calls made during the call are first-hand and outrank the transcript
    # read-back, so they are only filled in here, never overwritten.
    if session.confirmation_number is None:
        session.confirmation_number = extracted.get("confirmation_number")
    if session.new_rate is None and extracted.get("new_rate") is not None:
        session.new_rate = float(extracted["new_rate"])
    if session.previous_rate is None and extracted.get("previous_rate") is not None:
        session.previous_rate = float(extracted["previous_rate"])

    agreed = bool(extracted.get("agreed"))
    session.verified = agreed and session.new_rate is not None and session.previous_rate is not None
    session.verification_source = "assemblyai" if session.verified else "needs_human_review"
    session.status = NegotiationStatus.COMPLETED if agreed else NegotiationStatus.FAILED
    await save_session(session)

    events.publish(
        session.task_id,
        {
            "type": "verification",
            "verified": session.verified,
            "outcome": session.outcome,
            "new_rate": session.new_rate,
            "confirmation_number": session.confirmation_number,
        },
    )
    return session
