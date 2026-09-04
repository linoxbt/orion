"""The customer can hear the call that was made on their behalf.

Twilio holds the original behind account credentials the browser must never
see, and drops recordings when an account lapses - so a copy is kept in our
own private storage, keyed by owner and negotiation, and served through a
short-lived signed link.
"""

import pytest

from app.models import NegotiationStatus
from app.services import recordings
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}
INTRUDER = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "intruder"}


@pytest.fixture
def task_id(client) -> str:
    return client.post(
        "/api/negotiations/start",
        headers=HEADERS,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    ).json()["task_id"]


class TestPaths:
    def test_a_recording_is_filed_under_its_owner(self):
        """So a listing is scoped per account and two customers cannot collide."""
        assert recordings.object_path("user-1", "task-a") == "user-1/task-a.mp3"
        assert recordings.object_path("user-2", "task-a") == "user-2/task-a.mp3"

    def test_an_unowned_negotiation_cannot_collide_with_a_customer(self):
        assert recordings.object_path(None, "task-a") == "unowned/task-a.mp3"

    def test_the_link_expires(self):
        """A recorded phone call should not stay reachable forever."""
        assert 0 < recordings.SIGNED_URL_TTL_SECONDS <= 24 * 3600


class TestEndpoint:
    def test_nothing_to_play_before_a_call(self, client, task_id):
        res = client.get(f"/api/negotiations/{task_id}/recording", headers=HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert body["available"] is False
        assert body["reason"] == "no_call_yet"

    def test_a_finished_call_says_it_is_still_arriving(self, client, task_id):
        import asyncio

        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.status = NegotiationStatus.COMPLETED
        asyncio.run(save_session(session))

        body = client.get(f"/api/negotiations/{task_id}/recording", headers=HEADERS).json()
        assert body["available"] is False
        assert body["reason"] == "awaiting_recording"

    def test_a_stored_recording_is_playable(self, client, task_id, monkeypatch):
        import asyncio

        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.status = NegotiationStatus.COMPLETED
        session.recording_path = "owner/abc.mp3"
        asyncio.run(save_session(session))

        async def fake_url(path):
            assert path == "owner/abc.mp3"
            return "https://storage.example/signed"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        body = client.get(f"/api/negotiations/{task_id}/recording", headers=HEADERS).json()
        assert body["available"] is True
        assert body["url"] == "https://storage.example/signed"
        assert body["expires_in"] == recordings.SIGNED_URL_TTL_SECONDS

    def test_a_stranger_cannot_listen_to_your_call(self, client, task_id, monkeypatch):
        """The whole point of the ownership check: a recording is a phone call
        about somebody's account."""
        import asyncio

        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.recording_path = "owner/abc.mp3"
        asyncio.run(save_session(session))

        called = {"n": 0}

        async def fake_url(path):
            called["n"] += 1
            return "https://storage.example/signed"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        res = client.get(f"/api/negotiations/{task_id}/recording", headers=INTRUDER)
        assert res.status_code == 404
        assert called["n"] == 0, "a link must not even be minted for a stranger"

    def test_storage_being_unavailable_is_reported_not_crashed(self, client, task_id, monkeypatch):
        import asyncio

        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.recording_path = "owner/abc.mp3"
        asyncio.run(save_session(session))

        async def no_url(path):
            return None

        monkeypatch.setattr(recordings, "playback_url", no_url)
        body = client.get(f"/api/negotiations/{task_id}/recording", headers=HEADERS).json()
        assert body["available"] is False
        assert body["reason"] == "unavailable"
