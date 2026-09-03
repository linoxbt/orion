"""The signed-in customer's own details.

Everything a negotiation needs to know about a person that isn't on the bill:
who they are, where they live, how to reach them. Kept once so it can prefill
every negotiation instead of being retyped, and so a call can answer "what's
the address on the account?" without the customer having entered it a fourth
time.

Scoped by the Dynamic user id the proxy has already verified - see
app/security.py's require_user_id for why that identity can be trusted.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models import UserProfile
from app.security import require_user_id
from app.services import demo_seed, supabase_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    """Every field optional: the account page saves what changed, and a blank
    field means "not set", not "wipe the rest of the profile"."""

    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    country: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    preferred_language: str | None = None
    escalation_whatsapp: str | None = None
    escalation_email: str | None = None


@router.get("", response_model=UserProfile)
async def read_profile(user_id: str = Depends(require_user_id)) -> UserProfile:
    """The caller's profile, created empty on first visit.

    Returning an empty profile rather than a 404 keeps the account page simple:
    it always has something to render and edit, and a first-time user isn't
    shown an error for having done nothing wrong.
    """
    if not supabase_store.is_configured():
        raise HTTPException(status_code=503, detail="supabase_not_configured")

    profile = await supabase_store.get_profile(user_id)
    if profile is None:
        # First visit. Seed worked examples so the dashboard is not an empty
        # page, then create the profile so this only ever happens once.
        await demo_seed.seed_if_new(user_id)
        await supabase_store.ensure_profile(user_id)
        return UserProfile(id=user_id)
    return profile


@router.put("", response_model=UserProfile)
async def save_profile(
    body: ProfileUpdate, user_id: str = Depends(require_user_id)
) -> UserProfile:
    """Save the account page. Merges rather than replaces."""
    if not supabase_store.is_configured():
        raise HTTPException(status_code=503, detail="supabase_not_configured")

    existing = await supabase_store.get_profile(user_id) or UserProfile(id=user_id)
    changes = body.model_dump(exclude_unset=True)

    # An empty string from a cleared input means "unset this", which is
    # different from the field simply not being submitted.
    for field, value in changes.items():
        setattr(existing, field, value.strip() or None if isinstance(value, str) else value)

    # The id is the caller's, never the body's - so a crafted request can't
    # write into somebody else's profile.
    existing.id = user_id
    return await supabase_store.upsert_profile(existing)
