import hashlib
import hmac
import time
from functools import lru_cache

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from app.config import settings
from app.models import NegotiationSession


class TwilioNotConfigured(RuntimeError):
    pass


@lru_cache
def get_client() -> Client:
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise TwilioNotConfigured("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN are not set")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def voice_webhook_url(task_id: str) -> str:
    """The exact URL Twilio is given for a call's /telephony/voice webhook -
    shared by place_outbound_call (to set it) and the webhook handler itself
    (to validate X-Twilio-Signature against it). Built from settings.base_url
    rather than trusting the incoming request's observed URL, which can be
    wrong behind a reverse proxy.
    """
    return f"{settings.base_url}/telephony/voice?taskId={task_id}"


def recording_webhook_url(task_id: str) -> str:
    """The exact URL Twilio is given for a call's recording callback - set on
    the call and validated against on the way back in, same as the voice
    webhook above.
    """
    return f"{settings.base_url}/telephony/recording?taskId={task_id}"


def validate_signature(url: str, params: dict[str, str], signature: str) -> bool:
    """Verifies a request claiming to be Twilio actually is (architecture doc
    Section 6: outbound-call trigger endpoints must be authenticated). Fails
    closed if Twilio isn't configured - there's no auth token to validate
    against, and no real calls exist to receive a legitimate webhook for.
    """
    if not settings.twilio_auth_token:
        return False
    return RequestValidator(settings.twilio_auth_token).validate(url, params, signature)


def place_outbound_call(session: NegotiationSession) -> str:
    """Places the outbound call and points Twilio at /telephony/voice, which
    returns TwiML opening the Media Stream back to /telephony/stream for the
    live AssemblyAI bridge (architecture doc Section 3, Option A).
    """
    if not settings.twilio_phone_number:
        raise TwilioNotConfigured("TWILIO_PHONE_NUMBER is not set")
    client = get_client()
    call = client.calls.create(
        to=session.phone_number,
        from_=settings.twilio_phone_number,
        url=voice_webhook_url(session.task_id),
        # The recording is the evidence the post-call verification pass runs on
        # (app/services/verification.py) - without it a negotiated saving can't
        # be verified, and an unverified saving is never billed.
        record=True,
        recording_status_callback=recording_webhook_url(session.task_id),
        recording_status_callback_event=["completed"],
    )
    return call.sid


# --- Media Stream authentication -------------------------------------------
#
# Twilio signs its HTTP webhooks, but it cannot sign a WebSocket upgrade: the
# media stream arrives with nothing but the URL. So /telephony/stream accepted
# any connection quoting a task id, which meant anyone who knew or guessed one
# could open the bridge - joining a stranger's live call audio in both
# directions, and opening a billable AssemblyAI session per connection.
#
# The fix is a token minted into the stream URL at the moment the TwiML is
# built. That only happens inside the voice webhook, which is signature-checked
# already, so possession of a valid token means Twilio really was told to dial
# this call. It expires quickly because Twilio opens the stream immediately.

STREAM_TOKEN_TTL_SECONDS = 300


def _stream_secret() -> str:
    return settings.admin_api_key or ""


def mint_stream_token(task_id: str, *, now: float | None = None) -> str:
    """A short-lived token binding a stream URL to one task id."""
    secret = _stream_secret()
    if not secret:
        raise TwilioNotConfigured("ADMIN_API_KEY is not set; streams cannot be signed")
    expires = int((now if now is not None else time.time()) + STREAM_TOKEN_TTL_SECONDS)
    payload = f"{task_id}.{expires}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{digest}"


def verify_stream_token(task_id: str, token: str | None, *, now: float | None = None) -> bool:
    """Fails closed: an unsigned deployment gets no stream, rather than an
    open one."""
    secret = _stream_secret()
    if not secret or not token:
        return False

    expires_raw, _, digest = token.partition(".")
    if not digest:
        return False
    try:
        expires = int(expires_raw)
    except ValueError:
        return False

    if (now if now is not None else time.time()) > expires:
        return False

    expected = hmac.new(
        secret.encode(), f"{task_id}.{expires}".encode(), hashlib.sha256
    ).hexdigest()
    # Constant time: a fast reject leaks how much of the digest was right.
    return hmac.compare_digest(expected, digest)
