from fastapi import (
    APIRouter,
    BackgroundTasks,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
)
from twilio.twiml.voice_response import Connect, VoiceResponse

import logging
from datetime import datetime, timezone

from app.config import settings
from app.models import NegotiationSession, NegotiationStatus
from app.services import events
from app.services.live_bridge import run_bridge
from app.services.twilio_client import (
    stream_websocket_url,
    status_webhook_url,
    recording_webhook_url,
    validate_signature,
    verify_stream_token,
    voice_webhook_url,
)
from app.services.verification import apply_transcript, ingest_recording
from app.store import get_session, mutate, save_session

# How a call can end, and what to record when it does. "completed" is the only
# one that means a conversation actually happened.
def _attempt_for(session, call_sid: str | None):
    """The dial a webhook belongs to, by SID.

    Falls back to the most recent attempt only when the SID is unknown, so a
    stray callback cannot silently rewrite a different call's record.
    """
    if call_sid:
        for attempt in reversed(session.attempts):
            if attempt.call_sid == call_sid:
                return attempt
    return session.attempts[-1] if session.attempts else None


_ENDED_STATUSES = {
    "completed": "",
    "busy": "The line was busy.",
    "no-answer": "Nobody answered.",
    "failed": "The call could not be connected.",
    "canceled": "The call was cancelled before it connected.",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])


@router.post("/voice")
async def voice_webhook(
    request: Request, taskId: str = Query(...), x_twilio_signature: str | None = Header(default=None)
) -> Response:
    """Twilio hits this once the outbound call connects. Returns TwiML that
    opens a Media Stream back to /telephony/stream for the real-time AssemblyAI
    bridge (architecture doc Section 3, Option A).

    Validates X-Twilio-Signature against the exact URL Twilio was given (see
    app/services/twilio_client.voice_webhook_url) rather than the request's
    observed URL, which can be wrong behind a reverse proxy - an
    unauthenticated call-trigger webhook is the exact footgun the architecture
    doc's Section 6 security note calls out.
    """
    if not settings.twilio_auth_token:
        raise HTTPException(status_code=503, detail="twilio_not_configured")

    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    if not x_twilio_signature or not validate_signature(voice_webhook_url(taskId), params, x_twilio_signature):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")

    response = VoiceResponse()
    connect = Connect()
    # Signed, because the WebSocket itself carries no Twilio signature. Built
    # as a single path with no query string: two query parameters need an "&",
    # which this XML escapes to "&amp;" and Twilio passes through literally,
    # which is what silently broke every real call.
    connect.stream(url=stream_websocket_url(taskId))
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/stream/{task_id}/{token}")
async def media_stream(websocket: WebSocket, task_id: str, token: str) -> None:
    """Bidirectional audio bridge for one active call - see
    app/services/live_bridge.py, which picks the AssemblyAI voice backend.

    Audio is not resampled in either direction any more: both backends speak
    Twilio's native 8kHz mu-law, so the old audioop conversion layer is gone.

    The task id and token are PATH segments, not query parameters, and that is
    load-bearing rather than stylistic. With two query parameters the URL needs
    an "&", the TwiML serialiser escapes it to "&amp;", and Twilio passes that
    through literally - so the second parameter arrived named "amp;token", the
    token looked missing, this handler refused the socket, and because
    <Connect> is a terminal verb Twilio hung up the moment the call was
    answered. A single path has nothing to escape.
    """
    taskId = task_id  # the rest of this function reads better in one spelling

    # Twilio cannot sign a WebSocket upgrade, so the token minted into this
    # URL by the (signature-checked) voice webhook is what proves the
    # connection belongs to a real call. Without it, knowing a task id was
    # enough to join a stranger's live call and open a billable session.
    # Both refusals below close before accepting, which the client sees as a
    # bare HTTP 403 with no reason attached, so each one says which it was.
    if not verify_stream_token(taskId, token):
        logger.warning(
            "Media stream refused for %s: %s",
            taskId,
            "no token in the stream URL" if not token else "token did not verify",
        )
        await websocket.close(code=1008, reason="invalid_stream_token")
        return

    session = await get_session(taskId)
    if session is None:
        logger.warning("Media stream refused for %s: no such negotiation", taskId)
        await websocket.close(code=1008, reason="unknown_task_id")
        return

    logger.info("Media stream accepted for %s", taskId)
    await run_bridge(websocket, session)


@router.post("/recording")
async def recording_webhook(
    request: Request,
    background: BackgroundTasks,
    taskId: str = Query(...),
    x_twilio_signature: str | None = Header(default=None),
) -> dict[str, str]:
    """Twilio posts here once a call's recording is ready to download.

    The recording is what the post-call verification pass runs on (see
    app/services/verification.py), so this is the trigger for turning a
    finished call into a verified outcome. Downloading and transcribing takes
    far longer than a webhook should block for, so it's handed to a background
    task and this returns immediately.
    """
    if not settings.twilio_auth_token:
        raise HTTPException(status_code=503, detail="twilio_not_configured")

    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    if not x_twilio_signature or not validate_signature(
        recording_webhook_url(taskId), params, x_twilio_signature
    ):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")

    session = await get_session(taskId)
    if session is None:
        raise HTTPException(status_code=404, detail="not_found")

    recording_url = params.get("RecordingUrl")
    if not recording_url:
        raise HTTPException(status_code=422, detail="missing_recording_url")

    # Twilio reports how long it actually recorded. A call nobody answered
    # still produces a recording of a second or two, and transcribing that is
    # how the agent came to "report" a conversation that never happened.
    try:
        duration = int(params.get("RecordingDuration") or 0)
    except ValueError:
        duration = 0

    call_sid = params.get("CallSid")

    def record_duration(current: NegotiationSession) -> None:
        attempt = _attempt_for(current, call_sid)
        if attempt:
            attempt.duration_seconds = duration

    session = await mutate(taskId, record_duration) or session

    # The SID travels with it: a recording belongs to the dial it came from,
    # and a retry placed while this was in flight would otherwise file it
    # against the wrong attempt.
    background.add_task(ingest_recording, session, recording_url, duration, call_sid)
    return {"status": "accepted"}


@router.post("/transcript")
async def transcript_webhook(
    request: Request,
    background: BackgroundTasks,
    taskId: str = Query(...),
    x_orion_admin_key: str | None = Header(default=None),
) -> dict[str, str]:
    """AssemblyAI posts here when a transcript finishes.

    AssemblyAI has no request signing, so the submission sets a custom auth
    header (see verification.ingest_recording) and this checks it. The payload
    carries only {transcript_id, status} - the transcript itself is fetched
    separately. Handlers must answer 2xx inside 10 seconds or the delivery is
    retried, so the extraction runs in the background.
    """
    if not settings.admin_api_key or x_orion_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="invalid_webhook_auth")

    session = await get_session(taskId)
    if session is None:
        raise HTTPException(status_code=404, detail="not_found")

    body = await request.json()
    if body.get("status") != "completed":
        return {"status": "ignored"}

    transcript_id = body.get("transcript_id")
    if not transcript_id:
        raise HTTPException(status_code=422, detail="missing_transcript_id")

    background.add_task(apply_transcript, session, transcript_id)
    return {"status": "accepted"}


@router.post("/status")
async def status_webhook(
    request: Request,
    taskId: str = Query(...),
    x_twilio_signature: str | None = Header(default=None),
) -> dict[str, str]:
    """Twilio's report on how the call is going.

    This is what the on-screen call was missing entirely. Orion set the status
    to "calling" the moment the REST call was accepted and never heard another
    word, so the timer started while the phone was still ringing and the screen
    stayed live after the far end had hung up.

    CallStatus arrives as one of: queued, initiated, ringing, in-progress,
    completed, busy, no-answer, failed, canceled.
    """
    if not settings.twilio_auth_token:
        raise HTTPException(status_code=503, detail="twilio_not_configured")

    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    if not x_twilio_signature or not validate_signature(
        status_webhook_url(taskId), params, x_twilio_signature
    ):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")

    session = await get_session(taskId)
    if session is None:
        # Answering 2xx anyway: a retry cannot make a missing session appear,
        # and Twilio retries anything else.
        return {"status": "ignored"}

    call_status = params.get("CallStatus", "")
    # Which dial this is about. Matching on the SID rather than assuming the
    # last one keeps a late webhook from a previous attempt off the current
    # one's record.
    call_sid = params.get("CallSid")
    events.publish(taskId, {"type": "call_status", "status": call_status})

    def answered(current: NegotiationSession) -> None:
        # This is the only place answered_at is written, and it is what the
        # screen keys the timer off - `status` is already CALLING from the
        # moment dialling was accepted, so it cannot tell the two apart.
        current.status = NegotiationStatus.CALLING
        now = datetime.now(timezone.utc).isoformat()
        if not current.answered_at:
            current.answered_at = now
        attempt = _attempt_for(current, call_sid)
        if attempt and not attempt.answered_at:
            attempt.answered_at = now

    def ended(current: NegotiationSession) -> None:
        # The call is over however it ended, so the screen must not stay live.
        #
        # PENDING counts as still-live here as well as CALLING. The bridge's
        # own teardown moves a finished call back to PENDING while it waits for
        # the recording, and it usually wins the race with this webhook -
        # so requiring CALLING meant a completed call sat on the dashboard
        # reading "Pending" for good.
        if current.status in (NegotiationStatus.CALLING, NegotiationStatus.PENDING):
            current.status = (
                NegotiationStatus.COMPLETED
                if call_status == "completed"
                else NegotiationStatus.FAILED
            )
        if call_status != "completed" and not current.outcome:
            current.outcome = _ENDED_STATUSES[call_status]
        attempt = _attempt_for(current, call_sid)
        if attempt:
            attempt.ended_at = datetime.now(timezone.utc).isoformat()
            attempt.end_reason = call_status
            if not attempt.outcome and call_status != "completed":
                attempt.outcome = _ENDED_STATUSES[call_status]

    if call_status == "in-progress":
        await mutate(taskId, answered)
    elif call_status in _ENDED_STATUSES:
        await mutate(taskId, ended)
        events.publish(
            taskId,
            {"type": "status", "status": "call_ended", "reason": call_status},
        )

    return {"status": "accepted"}
