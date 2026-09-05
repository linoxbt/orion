from fastapi import APIRouter, Depends

from app.config import settings
from app.security import check_jwks_reachable, require_admin_key
from app.services import supabase_store

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness only. Which integrations are configured is operational detail,
    not something to advertise to anyone who curls the URL."""
    return {"ok": True, "version": "0.1.0"}


@router.get("/health/capabilities", dependencies=[Depends(require_admin_key)])
async def capabilities() -> dict:
    """What is wired up. Behind the admin key, and read by the settings page
    through the server-side proxy.

    `sessionsVerifiable` is the one worth watching: if Dynamic's keys can't be
    fetched, every signed-in request fails and the only symptom users see is
    being signed out. This makes that answerable directly instead of by
    inference from a 401, which looks identical either way.
    """
    return {
        "capabilities": {
            "sessionsVerifiable": await check_jwks_reachable(),
            # SQLite here means a local file, so on a container platform
            # the data lasts only as long as the disk it sits on.
            "persistence": "supabase" if supabase_store.is_configured() else "sqlite",
            "hasAssemblyAI": bool(settings.assemblyai_api_key),
            "voiceBackend": settings.voice_backend,
            "hasGemini": bool(settings.gemini_api_key),
            "hasTwilio": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            "hasStripe": bool(settings.stripe_secret_key),
            # Whether escalate_to_human can actually reach anybody. The tool
            # exists either way and is honest with the agent when it cannot,
            # but the account page should not invite somebody to enter a
            # number that nothing will ever message.
            "hasEscalation": bool(settings.sendgrid_api_key or settings.twilio_whatsapp_from),
        },
    }
