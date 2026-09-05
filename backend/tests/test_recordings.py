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


class TestListening:
    """Playback goes through /calls now - one entry per dial, each with its own
    signed link. The single-recording endpoint it replaced has been removed
    rather than left as a second way in."""

    def _with_recording(self, task_id: str, path: str | None = "owner/abc.mp3") -> None:
        import asyncio
        from datetime import datetime, timezone

        from app.models import CallAttempt
        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.status = NegotiationStatus.COMPLETED
        session.attempts.append(
            CallAttempt(
                call_sid="CA" + "1" * 32,
                started_at=datetime.now(timezone.utc).isoformat(),
                answered_at=datetime.now(timezone.utc).isoformat(),
                recording_path=path,
            )
        )
        asyncio.run(save_session(session))

    def test_nothing_to_play_before_a_call(self, client, task_id):
        res = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS)
        assert res.status_code == 200
        assert res.json() == []

    def test_a_call_with_no_recording_yet_is_listed_without_a_link(self, client, task_id):
        self._with_recording(task_id, path=None)
        [call] = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS).json()
        assert call["url"] is None
        assert call["answered"] is True

    def test_a_stored_recording_is_playable(self, client, task_id, monkeypatch):
        self._with_recording(task_id)

        async def fake_url(path):
            assert path == "owner/abc.mp3"
            return "https://storage.example/signed"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        [call] = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS).json()
        assert call["url"] == "https://storage.example/signed"
        assert call["download_name"].endswith(".mp3")

    def test_a_stranger_cannot_listen_to_your_call(self, client, task_id, monkeypatch):
        """The whole point of the ownership check: a recording is a phone call
        about somebody's account."""
        self._with_recording(task_id)
        called = {"n": 0}

        async def fake_url(path):
            called["n"] += 1
            return "https://storage.example/signed"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        res = client.get(f"/api/negotiations/{task_id}/calls", headers=INTRUDER)
        assert res.status_code == 404
        assert called["n"] == 0, "a link must not even be minted for a stranger"

    def test_storage_being_unavailable_leaves_the_call_listed(self, client, task_id, monkeypatch):
        """The call still happened; only the link is missing."""
        self._with_recording(task_id)

        async def no_url(path):
            return None

        monkeypatch.setattr(recordings, "playback_url", no_url)

        [call] = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS).json()
        assert call["url"] is None
        assert call["call_sid"] == "CA" + "1" * 32

    def test_a_negotiation_from_before_per_dial_attempts_still_shows_its_call(
        self, client, task_id, monkeypatch
    ):
        """Sessions created before attempts existed carry the recording on the
        session itself, and used to render as "No calls yet" beside audio that
        plainly existed."""
        import asyncio

        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.status = NegotiationStatus.COMPLETED
        session.call_sid = "CA" + "9" * 32
        session.recording_path = "owner/legacy.mp3"
        session.answered_at = "2026-09-01T10:00:00+00:00"
        asyncio.run(save_session(session))

        async def fake_url(path):
            return f"https://storage.example/{path}"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        [call] = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS).json()
        assert call["url"] == "https://storage.example/owner/legacy.mp3"
        assert call["answered"] is True
