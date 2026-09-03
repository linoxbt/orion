"""Who is calling, and what they are allowed to touch.

Two layers, and the distinction matters:

  require_admin_key  - proves a request came from our own server-side proxy
                       rather than straight off the internet. Says nothing
                       about who the request is for.
  require_user_id    - establishes *which person* the request is for, by
                       verifying their Dynamic session token against Dynamic's
                       published keys. Not by trusting a header.
  require_owned_session
                     - the one that actually protects data: loads the
                       negotiation and refuses unless it belongs to the caller.

The earlier design trusted an `X-Orion-User` header whenever the admin key was
present. That made the admin key a universal impersonation token: anything
holding it could act as any user. The token is now verified here, so a forged
or replayed header proves nothing on its own.
"""

import logging

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


async def require_admin_key(x_orion_admin_key: str | None = Header(default=None)) -> None:
    """Gates endpoints that place real calls or move real money (build spec
    Section 6's security note: an unauthenticated call-trigger endpoint means
    anyone who finds the URL can place calls billed to your account).

    Unconfigured means locked, not open - matches every other integration's
    honest "not configured" posture rather than defaulting to no protection.
    """
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="admin_api_key_not_configured")
    if x_orion_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="unauthorized")


# PyJWKClient caches keys and handles rotation, so it must be built once rather
# than per request.
_jwks_client: PyJWKClient | None = None

# PyJWKClient fetches over urllib, and Dynamic's edge answers 403 to its default
# User-Agent. Without this every token verification fails and every signed-in
# user gets a 401 - the whole application, not a corner of it.
_JWKS_HEADERS = {"User-Agent": "Orion/1.0 (+https://orionbuild.netlify.app)"}


def jwks_url() -> str:
    return (
        f"https://app.dynamic.xyz/api/v0/sdk/{settings.dynamic_environment_id}"
        "/.well-known/jwks"
    )


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            jwks_url(), cache_keys=True, headers=_JWKS_HEADERS, timeout=15
        )
    return _jwks_client


async def check_jwks_reachable() -> bool:
    """Called at startup so an unreachable JWKS is loud rather than silent.

    If key fetching fails, every verification fails, and the symptom is every
    user being signed out with no clue why. Better to say so in the logs on
    boot than to discover it one 401 at a time.
    """
    if not settings.dynamic_environment_id:
        logger.warning(
            "DYNAMIC_ENVIRONMENT_ID unset - sessions cannot be verified and the "
            "admin key becomes an impersonation token. Set it."
        )
        return False
    try:
        keys = _jwks().get_jwk_set()
        logger.info("Dynamic JWKS reachable (%s key(s))", len(keys.keys))
        return True
    except Exception as exc:  # noqa: BLE001 - startup diagnostics
        logger.error(
            "Dynamic JWKS is UNREACHABLE (%s). Every signed-in request will be "
            "rejected until this is fixed: %s",
            jwks_url(),
            exc,
        )
        return False


def _verify_dynamic_token(token: str) -> str:
    """Return the subject of a valid Dynamic session token, or raise."""
    try:
        signing_key = _jwks().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # Dynamic does not set an audience we can pin, so signature,
            # expiry and subject are what we rely on.
            options={"verify_aud": False, "require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected a session token: %s", exc)
        raise HTTPException(status_code=401, detail="invalid_session") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="invalid_session")
    return subject


async def require_user_id(
    x_orion_admin_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    x_orion_user: str | None = Header(default=None),
) -> str:
    """The verified identity of the person this request is for.

    The bearer token is the authority. `X-Orion-User` is accepted only as a
    fallback for deployments that have no Dynamic environment configured - in
    which case the admin key is all there is, and that limitation is logged
    rather than hidden.
    """
    await require_admin_key(x_orion_admin_key)

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token and settings.dynamic_environment_id:
        return _verify_dynamic_token(token)

    if settings.dynamic_environment_id:
        # A configured deployment must not fall back to an unverified header -
        # that is the impersonation hole this function exists to close.
        raise HTTPException(status_code=401, detail="no_verified_session")

    user_id = (x_orion_user or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="no_user_identity")
    logger.warning(
        "DYNAMIC_ENVIRONMENT_ID unset - trusting an unverified user header. "
        "Set it so sessions are actually verified."
    )
    return user_id


async def require_owned_session(
    task_id: str, user_id: str = Depends(require_user_id)
):
    """Load a negotiation and refuse unless it belongs to the caller.

    Every `/{task_id}/...` route needs this. Without it, knowing a task id was
    enough to read someone's negotiation, write verification details onto it,
    consent on their behalf, and place a real phone call - all of which were
    reachable with any valid session.

    A negotiation belonging to someone else answers 404, not 403: a 403 would
    confirm the id exists.
    """
    from app.store import get_session  # imported here to avoid a cycle

    session = await get_session(task_id)
    if session is None:
        raise HTTPException(status_code=404, detail="not_found")

    # An unowned session is one created before ownership existed. The comment
    # here used to say such a session was "claimed by the first caller" - but
    # nothing ever wrote an owner, so in practice every signed-in user could
    # read, consent on, and place calls against all of them indefinitely. They
    # are refused instead: every session created since /start required an
    # identity has an owner, so the only rows this can affect are old ones.
    if session.user_id is None or session.user_id != user_id:
        logger.warning(
            "Refused cross-user access to %s by %s", task_id, user_id
        )
        raise HTTPException(status_code=404, detail="not_found")

    return session
