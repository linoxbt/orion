"""Keeping the call recording, so the customer can hear it.

Twilio holds the recording behind HTTP basic auth on the account credentials,
which the browser must never see. And Twilio is not an archive: recordings are
deleted when an account lapses or is cleaned up, and they cost storage there.

So each recording is copied once into our own private bucket, keyed by owner
and negotiation, and served through a short-lived signed URL. The customer can
play back what the agent actually said on their behalf, and nothing about the
Twilio account reaches the page.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BUCKET = "call-recordings"

# Long enough to listen to a whole call, short enough that a copied link is
# not a permanent handle on somebody's phone call.
SIGNED_URL_TTL_SECONDS = 3600


def is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def _storage_base() -> str:
    return settings.supabase_url.rstrip("/") + "/storage/v1"


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    key = settings.supabase_service_key
    return {
        "apikey": key,
        "authorization": f"Bearer {key}",
        **(extra or {}),
    }


def object_path(user_id: str | None, task_id: str) -> str:
    """One recording per negotiation, filed under its owner.

    The owner is in the path so a listing is scoped per account, and an
    unowned negotiation cannot collide with a real customer's file.
    """
    return f"{user_id or 'unowned'}/{task_id}.mp3"


async def store(user_id: str | None, task_id: str, audio: bytes) -> str | None:
    """Copy a recording into our own bucket. Returns the stored path."""
    if not is_configured():
        return None

    path = object_path(user_id, task_id)
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            f"{_storage_base()}/object/{BUCKET}/{path}",
            headers=_headers({"content-type": "audio/mpeg", "x-upsert": "true"}),
            content=audio,
        )
    if res.status_code >= 400:
        logger.warning("Could not store the recording for %s: %s", task_id, res.text[:200])
        return None

    logger.info("Stored the recording for %s (%s bytes)", task_id, len(audio))
    return path


async def playback_url(path: str) -> str | None:
    """A short-lived URL the browser can play.

    Signed rather than public: a recording is a phone call about somebody's
    account, so the link expires instead of being guessable forever.
    """
    if not is_configured():
        return None

    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(
            f"{_storage_base()}/object/sign/{BUCKET}/{path}",
            headers=_headers({"content-type": "application/json"}),
            json={"expiresIn": SIGNED_URL_TTL_SECONDS},
        )
    if res.status_code >= 400:
        logger.warning("Could not sign a playback URL for %s: %s", path, res.text[:200])
        return None

    signed = (res.json() or {}).get("signedURL")
    if not signed:
        return None
    return settings.supabase_url.rstrip("/") + "/storage/v1" + signed
