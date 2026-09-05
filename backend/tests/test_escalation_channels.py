"""Three ways to reach somebody mid-call, and what each one costs to have.

The feature shipped able to reach nobody: it wanted a SendGrid key, whose free
tier was retired in May 2025, or a WhatsApp sender, which needs Meta Business
verification. Neither was configured, so escalate_to_human set a flag and told
the agent honestly that no one had been reached.

SMS closes that with nothing new signed up for: it goes out from the Twilio
number that placed the call.
"""

import asyncio

import pytest

from app.config import settings
from app.models import NegotiationSession
from app.services import notify


def _session() -> NegotiationSession:
    return NegotiationSession(
        task_id="task-1", provider="Comcast", phone_number="+15551234567", user_id=None
    )


def _capture(monkeypatch) -> dict:
    """Records the one outbound request instead of making it."""
    sent: dict = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, auth=None, data=None, json=None, headers=None):
            sent.update(url=url, auth=auth, data=data, json=json, headers=headers)
            return Response()

    monkeypatch.setattr(notify.httpx, "AsyncClient", lambda **kw: Client())
    return sent


class TestSms:
    @pytest.fixture(autouse=True)
    def _twilio(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
        monkeypatch.setattr(settings, "twilio_auth_token", "token")
        monkeypatch.setattr(settings, "twilio_phone_number", "+15550000000")

    def test_it_goes_out_from_the_number_that_places_the_calls(self, monkeypatch):
        sent = _capture(monkeypatch)
        assert asyncio.run(notify._send_sms("Orion needs you.", "+2347000000000")) is True
        assert sent["data"]["From"] == "+15550000000"
        assert sent["data"]["To"] == "+2347000000000"
        assert "AC123" in sent["url"]

    def test_it_is_trimmed_rather_than_billed_by_the_page(self, monkeypatch):
        sent = _capture(monkeypatch)
        asyncio.run(notify._send_sms("x" * 5000, "+2347000000000"))
        assert len(sent["data"]["Body"]) <= 640

    def test_no_number_means_nothing_is_sent(self, monkeypatch):
        _capture(monkeypatch)
        assert asyncio.run(notify._send_sms("body", None)) is False

    def test_an_unconfigured_deployment_sends_nothing(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_phone_number", "")
        _capture(monkeypatch)
        assert asyncio.run(notify._send_sms("body", "+2347000000000")) is False


class TestWhatsApp:
    @pytest.fixture(autouse=True)
    def _twilio(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
        monkeypatch.setattr(settings, "twilio_auth_token", "token")

    def test_the_sandbox_sender_is_accepted_already_prefixed(self, monkeypatch):
        """Twilio's console shows the sandbox number as whatsapp:+14155238886,
        and pasting it verbatim used to produce whatsapp:whatsapp:+1415..."""
        monkeypatch.setattr(settings, "twilio_whatsapp_from", "whatsapp:+14155238886")
        sent = _capture(monkeypatch)

        asyncio.run(notify._send_whatsapp("body", "+2347000000000"))

        assert sent["data"]["From"] == "whatsapp:+14155238886"
        assert sent["data"]["To"] == "whatsapp:+2347000000000"

    def test_a_bare_sender_is_prefixed(self, monkeypatch):
        monkeypatch.setattr(settings, "twilio_whatsapp_from", "+14155238886")
        sent = _capture(monkeypatch)
        asyncio.run(notify._send_whatsapp("body", "+2347000000000"))
        assert sent["data"]["From"] == "whatsapp:+14155238886"


class TestEmail:
    def test_it_uses_resend(self, monkeypatch):
        monkeypatch.setattr(settings, "resend_api_key", "re_test")
        monkeypatch.setattr(settings, "escalation_email_from", "Orion <alerts@useorion.xyz>")
        sent = _capture(monkeypatch)

        assert asyncio.run(notify._send_email("subject", "body", "me@example.com")) is True

        assert sent["url"] == notify.RESEND_URL
        assert sent["headers"]["Authorization"] == "Bearer re_test"
        assert sent["json"]["to"] == ["me@example.com"]
        assert sent["json"]["from"] == "Orion <alerts@useorion.xyz>"

    def test_an_unverified_deployment_falls_back_to_resends_own_sender(self, monkeypatch):
        monkeypatch.setattr(settings, "resend_api_key", "re_test")
        monkeypatch.setattr(settings, "escalation_email_from", "")
        sent = _capture(monkeypatch)

        asyncio.run(notify._send_email("subject", "body", "me@example.com"))

        assert "resend.dev" in sent["json"]["from"]

    def test_no_key_means_nothing_is_sent(self, monkeypatch):
        monkeypatch.setattr(settings, "resend_api_key", "")
        _capture(monkeypatch)
        assert asyncio.run(notify._send_email("s", "b", "me@example.com")) is False


class TestDeliveryOrder:
    def test_sms_is_tried_first(self, monkeypatch):
        """It has no session window, so it is the one most likely to arrive
        when somebody is not already in a conversation with us."""
        order: list[str] = []

        async def sms(body, to):
            order.append("SMS")
            return True

        async def whatsapp(body, to):
            order.append("WhatsApp")
            return True

        async def email(subject, body, to):
            order.append("email")
            return True

        monkeypatch.setattr(notify, "_send_sms", sms)
        monkeypatch.setattr(notify, "_send_whatsapp", whatsapp)
        monkeypatch.setattr(notify, "_send_email", email)
        monkeypatch.setattr(settings, "escalation_sms_to", "+15551110000")
        monkeypatch.setattr(settings, "escalation_whatsapp_to", "+15551110000")
        monkeypatch.setattr(settings, "escalation_email_to", "me@example.com")

        delivered = asyncio.run(notify.escalate(_session(), "needs a PIN"))

        assert order == ["SMS", "WhatsApp", "email"]
        assert delivered == ["SMS", "WhatsApp", "email"]

    def test_one_channel_failing_does_not_stop_the_others(self, monkeypatch):
        async def broken(*a, **kw):
            raise RuntimeError("twilio is down")

        async def works(*a, **kw):
            return True

        monkeypatch.setattr(notify, "_send_sms", broken)
        monkeypatch.setattr(notify, "_send_whatsapp", works)
        monkeypatch.setattr(notify, "_send_email", works)
        monkeypatch.setattr(settings, "escalation_sms_to", "+1")
        monkeypatch.setattr(settings, "escalation_whatsapp_to", "+1")
        monkeypatch.setattr(settings, "escalation_email_to", "me@example.com")

        assert asyncio.run(notify.escalate(_session(), "x")) == ["WhatsApp", "email"]
