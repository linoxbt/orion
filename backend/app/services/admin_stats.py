"""What the operator needs to know about the whole protocol, in one read.

Every figure here comes from the database or a live integration check. Nothing
is estimated, and anything that cannot be determined is reported as unknown
rather than as zero - a dashboard that shows a confident 0 for something it
failed to read is worse than one that says it does not know.
"""

import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.services import paystack, quota, recordings, supabase_store
from app.services.assemblyai import REST_BASE, rest_headers

logger = logging.getLogger(__name__)


async def _profiles() -> list[dict[str, Any]]:
    if not supabase_store.is_configured():
        return []
    res = await supabase_store._http().get(
        f"{supabase_store._base()}/profiles",
        headers=supabase_store._headers(),
        params={"select": "*", "limit": "1000"},
    )
    res.raise_for_status()
    return res.json()


async def _negotiations() -> list[dict[str, Any]]:
    if not supabase_store.is_configured():
        return []
    res = await supabase_store._http().get(
        f"{supabase_store._base()}/negotiations",
        headers=supabase_store._headers(),
        params={"select": "task_id,user_id,provider,status,language,data", "limit": "1000"},
    )
    res.raise_for_status()
    return res.json()


async def _assemblyai_reachable() -> bool | None:
    """None means we could not tell, which is different from 'down'."""
    if not settings.assemblyai_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{REST_BASE}/v2/transcript?limit=1", headers=rest_headers())
        return res.status_code < 400
    except Exception:  # noqa: BLE001 - a status probe must never raise
        return False


async def _twilio_account() -> dict[str, Any] | None:
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}.json",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
        if res.status_code >= 400:
            return None
        d = res.json()
        return {"type": d.get("type"), "status": d.get("status"), "name": d.get("friendly_name")}
    except Exception:  # noqa: BLE001
        return None


async def _payments() -> dict[str, Any] | None:
    """Recent transactions, straight from Paystack.

    Statuses matter here and are reported verbatim: a bank transfer can sit at
    reversal-pending, which is neither a success nor an abandonment, and
    flattening that into "failed" would hide the actual reason.
    """
    if not paystack.is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{paystack.API}/transaction",
                headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
                params={"perPage": 25},
            )
        if res.status_code >= 400:
            return None
        rows = (res.json() or {}).get("data") or []
    except Exception:  # noqa: BLE001
        return None

    by_status = Counter(r.get("status") or "unknown" for r in rows)
    settled = sum(
        (r.get("amount") or 0) for r in rows if r.get("status") == "success"
    ) / paystack.MINOR_UNITS

    return {
        "recent": [
            {
                "at": (r.get("created_at") or "")[:19].replace("T", " "),
                "status": r.get("status"),
                "amount": (r.get("amount") or 0) / paystack.MINOR_UNITS,
                "currency": r.get("currency"),
                "channel": r.get("channel"),
                "reference": r.get("reference"),
                "user_id": (r.get("metadata") or {}).get("user_id"),
            }
            for r in rows[:12]
        ],
        "by_status": dict(by_status),
        "settled": settled,
        "currency": settings.paystack_currency,
    }


def _rate(session: dict[str, Any], key: str) -> float | None:
    value = (session.get("data") or {}).get(key)
    return value if isinstance(value, (int, float)) else None


async def collect() -> dict[str, Any]:
    """One pass over everything the dashboard shows."""
    profiles, negotiations, aai, twilio, payments = await asyncio.gather(
        _profiles(),
        _negotiations(),
        _assemblyai_reachable(),
        _twilio_account(),
        _payments(),
        return_exceptions=True,
    )

    def ok(v, fallback):
        return fallback if isinstance(v, BaseException) else v

    profiles = ok(profiles, [])
    negotiations = ok(negotiations, [])
    aai = ok(aai, None)
    twilio = ok(twilio, None)
    payments = ok(payments, None)

    real = [n for n in negotiations if not (n.get("data") or {}).get("is_sample")]
    samples = len(negotiations) - len(real)

    by_status = Counter(n.get("status") or "unknown" for n in real)
    verified = [n for n in real if (n.get("data") or {}).get("verified")]
    with_recording = [n for n in real if (n.get("data") or {}).get("recording_path")]

    monthly_saving = 0.0
    for n in verified:
        before, after = _rate(n, "previous_rate"), _rate(n, "new_rate")
        if before is not None and after is not None and before > after:
            monthly_saving += before - after

    month = quota.current_month()
    pro = [p for p in profiles if p.get("plan") == "pro"]
    bills_used = sum(
        p.get("bills_used") or 0 for p in profiles if p.get("quota_month") == month
    )

    languages = Counter(n.get("language") or "en" for n in real)
    providers = Counter(n.get("provider") or "unknown" for n in real)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "integrations": {
            "AssemblyAI": {
                "configured": bool(settings.assemblyai_api_key),
                "reachable": aai,
                "detail": f"voice backend: {settings.voice_backend}",
            },
            "Gemini": {
                "configured": bool(settings.gemini_api_key),
                "reachable": None,
                "detail": "bill extraction",
            },
            "Twilio": {
                "configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
                "reachable": twilio is not None,
                "detail": (
                    f"{twilio['type']} account, {settings.twilio_phone_number}"
                    if twilio
                    else "no phone line"
                ),
            },
            "Supabase": {
                "configured": supabase_store.is_configured(),
                "reachable": bool(profiles) or supabase_store.is_configured(),
                "detail": "persistence and recordings",
            },
            "Paystack": {
                "configured": paystack.is_configured(),
                "reachable": payments is not None,
                "detail": f"{settings.paystack_currency} {settings.pro_price} a month",
            },
            "Dynamic": {
                "configured": bool(settings.dynamic_environment_id),
                "reachable": None,
                "detail": "session verification",
            },
            "Recording storage": {
                "configured": recordings.is_configured(),
                "reachable": None,
                "detail": f"bucket: {recordings.BUCKET}",
            },
        },
        "accounts": {
            "total": len(profiles),
            "pro": len(pro),
            "free": len(profiles) - len(pro),
            "bills_used_this_month": bills_used,
            "month": month,
            "free_allowance": quota.FREE_MONTHLY_BILLS,
        },
        "negotiations": {
            "total": len(real),
            "samples": samples,
            "by_status": dict(by_status),
            "verified": len(verified),
            "with_recording": len(with_recording),
            "monthly_saving": round(monthly_saving, 2),
            "languages": dict(languages.most_common(6)),
            "providers": dict(providers.most_common(8)),
            "recent": [
                {
                    "task_id": n.get("task_id"),
                    "provider": n.get("provider"),
                    "status": n.get("status"),
                    "user_id": n.get("user_id"),
                    "verified": bool((n.get("data") or {}).get("verified")),
                    "recording": bool((n.get("data") or {}).get("recording_path")),
                    "outcome": ((n.get("data") or {}).get("outcome") or "")[:90],
                }
                for n in real[:12]
            ],
        },
        "payments": payments,
    }
