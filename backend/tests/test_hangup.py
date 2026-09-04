"""Ending a call must end the call.

The on-screen End button closed the window and nothing else. The Twilio call
carried on - billing by the minute, with the agent still talking to the
provider - and the app offered no way to stop it.
"""

import pytest
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.models import NegotiationStatus
from app.services import twilio_client
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}


@pytest.fixture
def calling(client, monkeypatch) -> str:
    """A negotiation with a live call on it."""
    monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "0" * 32)
    monkeypatch.setattr(settings, "twilio_auth_token", "token")

    task_id = client.post(
        "/api/negotiations/start",
        headers=HEADERS,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    ).json()["task_id"]

    import asyncio

    from app.store import get_session, save_session

    session = asyncio.run(get_session(task_id))
    session.status = NegotiationStatus.CALLING
    session.call_sid = "CA" + "1" * 32
    asyncio.run(save_session(session))
    return task_id


def _fake_twilio(monkeypatch, on_update):
    class Call:
        def __init__(self, sid):
            self.sid = sid

        def update(self, **kwargs):
            return on_update(self.sid, kwargs)

    class Client:
        def calls(self, sid):
            return Call(sid)

    monkeypatch.setattr(twilio_client, "get_client", lambda: Client())


class TestHangup:
    def test_it_actually_tells_twilio_to_end_the_call(self, client, calling, monkeypatch):
        ended = {}
        _fake_twilio(monkeypatch, lambda sid, kw: ended.update(sid=sid, **kw))

        res = client.post(f"/api/negotiations/{calling}/hangup", headers=HEADERS)
        assert res.status_code == 200
        assert ended["sid"] == "CA" + "1" * 32
        assert ended["status"] == "completed"

    def test_the_negotiation_stops_showing_as_live(self, client, calling, monkeypatch):
        _fake_twilio(monkeypatch, lambda sid, kw: None)
        res = client.post(f"/api/negotiations/{calling}/hangup", headers=HEADERS)
        assert res.json()["status"] == "completed"
        assert res.json()["outcome"]

    def test_ending_an_already_finished_call_succeeds(self, client, calling, monkeypatch):
        """Idempotent: the caller wanted it down, and it is down."""
        def already_over(sid, kw):
            raise TwilioRestException(
                status=400, uri="/Calls", msg="Call is not in-progress. Cannot redirect.", code=21220
            )

        _fake_twilio(monkeypatch, already_over)
        assert client.post(f"/api/negotiations/{calling}/hangup", headers=HEADERS).status_code == 200

    def test_hanging_up_a_call_that_never_started_is_harmless(self, client):
        task_id = client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={"provider": "X", "phone_number": "+15551234567", "vertical": "cable_internet"},
        ).json()["task_id"]
        assert client.post(f"/api/negotiations/{task_id}/hangup", headers=HEADERS).status_code == 200

    def test_a_stranger_cannot_hang_up_your_call(self, client, calling):
        intruder = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "intruder"}
        assert client.post(f"/api/negotiations/{calling}/hangup", headers=intruder).status_code == 404

    def test_it_announces_the_end_on_the_live_feed(self, client, calling, monkeypatch):
        from app.services import events

        events._replay.clear()
        _fake_twilio(monkeypatch, lambda sid, kw: None)
        client.post(f"/api/negotiations/{calling}/hangup", headers=HEADERS)

        statuses = [e.get("status") for e in events._replay[calling]]
        assert "call_ended" in statuses
