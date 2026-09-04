"""Every call is kept, not just the most recent one.

A negotiation is dialled more than once - the first attempt frequently reaches
nobody - and the session carried a single recording_path, so each retry
overwrote the recording before it. Most of what was done on a customer's
behalf simply disappeared.
"""

import pytest

from app.config import settings
from app.services import recordings
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}
INTRUDER = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "intruder"}


class TestRecordingPaths:
    def test_two_calls_on_one_negotiation_do_not_collide(self):
        """The bug, at its source: the same path for every attempt."""
        first = recordings.object_path("u1", "task-a", "CA111")
        second = recordings.object_path("u1", "task-a", "CA222")
        assert first != second

    def test_a_path_is_still_scoped_to_its_owner(self):
        assert recordings.object_path("u1", "task-a", "CA1").startswith("u1/")
        assert recordings.object_path("u2", "task-a", "CA1").startswith("u2/")

    def test_it_still_works_without_a_call_sid(self):
        assert recordings.object_path("u1", "task-a") == "u1/task-a.mp3"


class TestCallList:
    @pytest.fixture
    def task_id(self, client, monkeypatch) -> str:
        monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "0" * 32)
        monkeypatch.setattr(settings, "twilio_auth_token", "token")
        return client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567",
                  "vertical": "cable_internet"},
        ).json()["task_id"]

    def test_a_negotiation_never_called_lists_nothing(self, client, task_id):
        res = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS)
        assert res.status_code == 200
        assert res.json() == []

    def test_every_attempt_is_listed_newest_first(self, client, task_id, monkeypatch):
        import asyncio

        from app.models import CallAttempt
        from app.store import get_session, save_session

        session = asyncio.run(get_session(task_id))
        session.attempts = [
            CallAttempt(call_sid="CA1", started_at="2026-09-04T10:00:00+00:00",
                        end_reason="no-answer", outcome="Nobody answered."),
            CallAttempt(call_sid="CA2", started_at="2026-09-04T11:00:00+00:00",
                        answered_at="2026-09-04T11:00:20+00:00", end_reason="completed",
                        duration_seconds=210, recording_path="owner/task-CA2.mp3"),
        ]
        asyncio.run(save_session(session))

        async def fake_url(path):
            return f"https://storage.example/{path}"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        rows = client.get(f"/api/negotiations/{task_id}/calls", headers=HEADERS).json()
        assert len(rows) == 2
        assert rows[0]["call_sid"] == "CA2", "newest first"
        assert rows[0]["answered"] is True
        assert rows[0]["url"].endswith("owner/task-CA2.mp3")
        assert rows[0]["download_name"].endswith(".mp3")

        # The unanswered attempt is still listed, with its reason and no audio.
        assert rows[1]["call_sid"] == "CA1"
        assert rows[1]["answered"] is False
        assert rows[1]["url"] is None
        assert rows[1]["outcome"] == "Nobody answered."

    def test_a_stranger_gets_no_list_and_no_links(self, client, task_id, monkeypatch):
        minted = {"n": 0}

        async def fake_url(path):
            minted["n"] += 1
            return "https://storage.example/x"

        monkeypatch.setattr(recordings, "playback_url", fake_url)

        res = client.get(f"/api/negotiations/{task_id}/calls", headers=INTRUDER)
        assert res.status_code == 404
        assert minted["n"] == 0
