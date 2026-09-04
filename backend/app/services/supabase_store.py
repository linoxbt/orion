"""Persistence in Supabase.

Replaces the SQLite file that lived on a single Railway volume - no backups,
one instance, and gone if the volume goes. It also gives negotiations an owner,
which SQLite never did: every signed-in user could previously list every
negotiation in the system, because sessions had no user attached at all.

Identity comes from Dynamic, not Supabase Auth, so `auth.uid()` is null in this
database and RLS cannot express "this row belongs to the caller". The tables
are therefore RLS-enabled with no permissive policies - a deliberate deny-all -
and everything here goes through the service role, scoping each query by a user
id the caller has already verified. A leaked publishable key opens nothing.
"""

import logging
from typing import Any

import uuid

import httpx

from app.config import settings
from app.models import NegotiationSession, UserProfile

logger = logging.getLogger(__name__)

# One pooled client for the process. Building an AsyncClient per call meant a
# fresh TLS handshake on every read and write.
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=20.0)
    return _client


async def aclose() -> None:
    """Called on shutdown so the pool is released cleanly."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class SupabaseNotConfigured(RuntimeError):
    pass


def _base() -> str:
    if not (settings.supabase_url and settings.supabase_service_key):
        raise SupabaseNotConfigured(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY are required for persistence"
        )
    return settings.supabase_url.rstrip("/") + "/rest/v1"


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    key = settings.supabase_service_key
    return {
        "apikey": key,
        "authorization": f"Bearer {key}",
        "content-type": "application/json",
        **(extra or {}),
    }


def is_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


# ---- profiles --------------------------------------------------------------


async def get_profile(user_id: str) -> UserProfile | None:
    res = await _http().get(
        f"{_base()}/profiles",
        headers=_headers(),
        params={"id": f"eq.{user_id}", "select": "*", "limit": 1},
    )
    res.raise_for_status()
    rows = res.json()
    return UserProfile.model_validate(rows[0]) if rows else None


async def ensure_profile(user_id: str) -> None:
    """Make sure a profile row exists for this user.

    negotiations.user_id is a foreign key into profiles, so without this the
    very first negotiation for any user fails outright:

        23503: insert or update on table "negotiations" violates foreign key
        constraint "negotiations_user_id_fkey"

    Every user starts with no profile row, so that was every user. The insert
    is a no-op when the row already exists.
    """
    res = await _http().post(
        f"{_base()}/profiles",
        headers=_headers({"prefer": "resolution=ignore-duplicates,return=minimal"}),
        params={"on_conflict": "id"},
        json={"id": user_id},
    )
    res.raise_for_status()


async def upsert_profile(profile: UserProfile) -> UserProfile:
    """Create or update. `updated_at` is maintained by a trigger, so it is
    excluded here rather than being overwritten with a client clock."""
    payload = profile.model_dump(exclude_none=True, exclude={"created_at", "updated_at"})

    res = await _http().post(
        f"{_base()}/profiles",
        headers=_headers({"prefer": "resolution=merge-duplicates,return=representation"}),
        params={"on_conflict": "id"},
        json=payload,
    )
    res.raise_for_status()
    rows = res.json()
    return UserProfile.model_validate(rows[0])


# ---- negotiations ----------------------------------------------------------


def _row_for(session: NegotiationSession) -> dict[str, Any]:
    """The full session in `data`, with a few columns alongside for querying.

    Keeping the Pydantic model as the source of truth means adding a field to a
    negotiation doesn't need a database migration.
    """
    return {
        "task_id": session.task_id,
        "user_id": session.user_id,
        "provider": session.provider,
        "phone_number": session.phone_number,
        "vertical": session.vertical,
        "language": session.language,
        "status": session.status.value,
        "data": session.model_dump(mode="json"),
    }


async def save_session(session: NegotiationSession) -> None:
    # The owner must exist before the negotiation can reference them.
    if session.user_id:
        await ensure_profile(session.user_id)

    res = await _http().post(
        f"{_base()}/negotiations",
        headers=_headers({"prefer": "resolution=merge-duplicates"}),
        params={"on_conflict": "task_id"},
        json=_row_for(session),
    )
    res.raise_for_status()


def _could_exist(task_id: str) -> bool:
    """Whether this id could name a row at all.

    negotiations.task_id is a uuid column, so PostgREST answers 400 (22P02,
    "invalid input syntax for type uuid") rather than an empty result for
    anything that is not one. That turned every malformed id into a 500:
    GET /api/receipts/<junk> was a server error any stranger could trigger,
    and the media-stream WebSocket rejected a real call's id with 500 instead
    of closing cleanly. An id that cannot match is simply not found.
    """
    try:
        uuid.UUID(task_id)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


async def get_session(task_id: str) -> NegotiationSession | None:
    if not _could_exist(task_id):
        return None

    res = await _http().get(
        f"{_base()}/negotiations",
        headers=_headers(),
        params={"task_id": f"eq.{task_id}", "select": "data", "limit": 1},
    )
    res.raise_for_status()
    rows = res.json()
    return NegotiationSession.model_validate(rows[0]["data"]) if rows else None


async def list_sessions(
    user_id: str | None = None, *, limit: int = 100, offset: int = 0
) -> list[NegotiationSession]:
    """Newest first, scoped to one user unless deliberately called without one.

    `user_id=None` returns everything and exists only for the renewals sweep,
    which runs server-side and is never exposed to a browser.
    """
    params: dict[str, str] = {
        "select": "data",
        "order": "created_at.desc",
        "limit": str(limit),
        "offset": str(offset),
    }
    if user_id is not None:
        params["user_id"] = f"eq.{user_id}"

    res = await _http().get(f"{_base()}/negotiations", headers=_headers(), params=params)
    res.raise_for_status()
    rows = res.json()
    return [NegotiationSession.model_validate(row["data"]) for row in rows]
