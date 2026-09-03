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

from app.config import settings
from app.services.live_bridge import run_bridge
from app.services.twilio_client import (
    mint_stream_token,
    recording_webhook_url,
    validate_signature,
    verify_stream_token,
    voice_webhook_url,
)
from app.services.verification import apply_transcript, ingest_recording
from app.store import get_session

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

    stream_url = settings.base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    response = VoiceResponse()
    connect = Connect()
    # Signed, because the WebSocket itself carries no Twilio signature.
    token = mint_stream_token(taskId)
    connect.stream(url=f"{stream_url}/telephony/stream?taskId={taskId}&token={token}")
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@router.websocket("/stream")
async def media_stream(
    websocket: WebSocket, taskId: str = Query(...), token: str | None = Query(default=None)
) -> None:
    """Bidirectional audio bridge for one active call - see
    app/services/live_bridge.py, which picks the AssemblyAI voice backend.

    Audio is not resampled in either direction any more: both backends speak
    Twilio's native 8kHz mu-law, so the old audioop conversion layer is gone.
    """
    # Twilio cannot sign a WebSocket upgrade, so the token minted into this
    # URL by the (signature-checked) voice webhook is what proves the
    # connection belongs to a real call. Without it, knowing a task id was
    # enough to join a stranger's live call and open a billable session.
    if not verify_stream_token(taskId, token):
        await websocket.close(code=1008, reason="invalid_stream_token")
        return

    session = await get_session(taskId)
    if session is None:
        await websocket.close(code=1008, reason="unknown_task_id")
        return
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

    background.add_task(ingest_recording, session, recording_url)
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
