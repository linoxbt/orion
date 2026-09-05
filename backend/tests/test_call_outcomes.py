"""What a negotiation's status is allowed to say about a call.

Two failures this pins down, both reported as the same thing to a customer:

  - A call that reached a representative, argued, and was refused used to be
    marked FAILED - the same red word as a number that never connected. The
    call did not fail; the negotiation did, which is what `verified` says.
  - A completed call could be left reading "Pending" forever, because the
    bridge's teardown moved it back to PENDING while it waited for the
    recording and the status webhook only promoted from CALLING.
"""

import asyncio

import pytest

from app.models import NegotiationSession, NegotiationStatus
from app.services import verification
from app.store import get_session, init_db, save_session
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}


def _session(**kw) -> NegotiationSession:
    base = dict(
        task_id="22222222-2222-2222-2222-222222222222",
        user_id="owner",
        provider="Comcast",
        phone_number="+15551234567",
        answered_at="2026-09-05T10:00:00+00:00",
    )
    base.update(kw)
    return NegotiationSession(**base)


@pytest.fixture
def store(isolated_db):
    asyncio.run(init_db())


def _extraction(monkeypatch, payload):
    async def fake(*a, **kw):
        return payload

    monkeypatch.setattr(verification, "llm_gateway_json", fake)

    async def transcript(_id):
        return {"status": "completed", "text": "hello", "utterances": []}

    monkeypatch.setattr(verification, "fetch_transcript", transcript)


class TestARefusalIsNotAFailedCall:
    def test_a_call_that_agreed_nothing_is_still_completed(self, store, monkeypatch):
        _extraction(
            monkeypatch,
            {"agreed": False, "outcome": "They would not move on the rate.", "recommendation": "Try again in a month."},
        )
        session = _session(status=NegotiationStatus.CALLING)
        asyncio.run(save_session(session))

        updated = asyncio.run(verification.apply_transcript(session, "t1"))

        assert updated.status is NegotiationStatus.COMPLETED
        assert updated.verified is False
        assert updated.outcome == "They would not move on the rate."

    def test_a_call_nobody_answered_stays_failed(self, store, monkeypatch):
        """The status webhook already established this one; it is not an
        interpretation the transcript may overturn."""
        _extraction(monkeypatch, {"agreed": False, "outcome": "Nothing happened."})
        session = _session(status=NegotiationStatus.FAILED)
        asyncio.run(save_session(session))

        updated = asyncio.run(verification.apply_transcript(session, "t1"))

        assert updated.status is NegotiationStatus.FAILED

    def test_a_win_is_completed_and_verified(self, store, monkeypatch):
        _extraction(
            monkeypatch,
            {
                "agreed": True,
                "outcome": "Agreed 69.99 for 12 months.",
                "previous_rate": 89.99,
                "new_rate": 69.99,
                "confirmation_number": "A1B2C3",
                "recommendation": "Check next month's bill shows 69.99.",
            },
        )
        session = _session(status=NegotiationStatus.FAILED)
        asyncio.run(save_session(session))

        updated = asyncio.run(verification.apply_transcript(session, "t1"))

        assert updated.status is NegotiationStatus.COMPLETED
        assert updated.verified is True
        assert updated.new_rate == 69.99


class TestALateWebhookStillEndsTheCall:
    def test_a_completed_call_left_pending_is_still_promoted(self, client, monkeypatch):
        """The bridge's teardown wins the race often enough that this is the
        normal case, not the edge case."""
        from app.config import settings
        from app.routers import telephony

        monkeypatch.setattr(settings, "twilio_auth_token", "token")
        monkeypatch.setattr(telephony, "validate_signature", lambda *a, **kw: True)

        task_id = client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        ).json()["task_id"]

        session = asyncio.run(get_session(task_id))
        session.status = NegotiationStatus.PENDING  # what start_verification leaves behind
        session.answered_at = "2026-09-05T10:00:00+00:00"
        asyncio.run(save_session(session))

        res = client.post(
            f"/telephony/status?taskId={task_id}",
            headers={"X-Twilio-Signature": "x"},
            data={"CallStatus": "completed", "CallSid": "CA" + "1" * 32},
        )
        assert res.status_code == 200

        assert asyncio.run(get_session(task_id)).status is NegotiationStatus.COMPLETED
