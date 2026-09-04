"""Twilio's call progress drives the screen.

Reported from a real call: the number rang, and Orion had already started
counting call time. Picking up and hanging up changed nothing - the app still
showed the call as live. Orion set the status to "calling" when the REST call
was accepted and then never heard from Twilio again, because the call was
created with no status callback at all.
"""

import pytest
from twilio.request_validator import RequestValidator

from app.config import settings
from app.services import events
from app.services.twilio_client import status_webhook_url
from tests.conftest import ADMIN_HEADERS, ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}


def _signed(url: str, params: dict[str, str]) -> dict[str, str]:
    return {"X-Twilio-Signature": RequestValidator(settings.twilio_auth_token).compute_signature(url, params)}


@pytest.fixture(autouse=True)
def _twilio(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "test-auth-token")


@pytest.fixture
def task_id(client) -> str:
    return client.post(
        "/api/negotiations/start",
        headers=HEADERS,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    ).json()["task_id"]


def _post(client, task_id: str, status: str):
    url = status_webhook_url(task_id)
    params = {"CallSid": "CA" + "0" * 32, "CallStatus": status}
    return client.post(f"/telephony/status?taskId={task_id}", data=params, headers=_signed(url, params))


class TestSignature:
    def test_an_unsigned_report_is_refused(self, client, task_id):
        res = client.post(f"/telephony/status?taskId={task_id}", data={"CallStatus": "completed"})
        assert res.status_code == 403

    def test_a_forged_signature_is_refused(self, client, task_id):
        res = client.post(
            f"/telephony/status?taskId={task_id}",
            data={"CallStatus": "completed"},
            headers={"X-Twilio-Signature": "forged"},
        )
        assert res.status_code == 403


class TestProgress:
    def setup_method(self):
        events._replay.clear()
        events._last_seen.clear()

    def test_ringing_is_reported_but_does_not_mark_the_call_answered(self, client, task_id):
        """The timer must not start here. This is the bug that counted seconds
        while the handset was still ringing."""
        assert _post(client, task_id, "ringing").status_code == 200

        session = client.get(f"/api/negotiations/{task_id}", headers=HEADERS).json()
        assert session["status"] == "pending"

        published = [e for e in events._replay[task_id] if e.get("type") == "call_status"]
        assert published[-1]["status"] == "ringing"

    def test_answering_marks_the_call_live(self, client, task_id):
        assert _post(client, task_id, "in-progress").status_code == 200
        session = client.get(f"/api/negotiations/{task_id}", headers=HEADERS).json()
        assert session["status"] == "calling"

    def test_hanging_up_ends_the_call(self, client, task_id):
        """The far end hung up and the app carried on showing a live call."""
        _post(client, task_id, "in-progress")
        _post(client, task_id, "completed")

        session = client.get(f"/api/negotiations/{task_id}", headers=HEADERS).json()
        assert session["status"] == "completed"

        statuses = [e.get("status") for e in events._replay[task_id]]
        assert "call_ended" in statuses

    @pytest.mark.parametrize(
        "status,expected",
        [("busy", "failed"), ("no-answer", "failed"), ("canceled", "failed"), ("failed", "failed")],
    )
    def test_every_way_a_call_can_fail_ends_the_screen(self, client, task_id, status, expected):
        _post(client, task_id, "in-progress")
        assert _post(client, task_id, status).status_code == 200

        session = client.get(f"/api/negotiations/{task_id}", headers=HEADERS).json()
        assert session["status"] == expected
        assert session["outcome"], "an unanswered call should say why"

    def test_an_unknown_task_is_accepted_rather_than_retried(self, client):
        """Twilio retries a non-2xx, and no retry can conjure the session."""
        res = _post(client, "11111111-1111-1111-1111-111111111111", "completed")
        assert res.status_code == 200


class TestCallCreation:
    def test_the_call_asks_twilio_for_progress(self, monkeypatch):
        """Without these the webhook above is never called at all."""
        from app.models import NegotiationSession
        from app.services import twilio_client

        monkeypatch.setattr(settings, "twilio_phone_number", "+14647682206")
        captured = {}

        class FakeCalls:
            @staticmethod
            def create(**kwargs):
                captured.update(kwargs)
                return type("C", (), {"sid": "CA123"})()

        monkeypatch.setattr(
            twilio_client, "get_client", lambda: type("C", (), {"calls": FakeCalls()})()
        )

        session = NegotiationSession(
            task_id="11111111-1111-1111-1111-111111111111",
            provider="Comcast",
            phone_number="+15551234567",
        )
        twilio_client.place_outbound_call(session)

        assert "status_callback" in captured
        assert set(captured["status_callback_event"]) >= {"ringing", "answered", "completed"}
