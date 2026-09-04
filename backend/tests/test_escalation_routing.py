"""An escalation goes to the customer whose call it is.

Escalation contacts used to be deployment-wide environment variables, which is
single-tenant thinking in a multi-user product: one address would have been
paged about every customer's call, and told the provider and best offer from
negotiations belonging to strangers.
"""

import asyncio

import pytest

from app.config import settings
from app.models import NegotiationSession, UserProfile
from app.services import notify


def _session(user_id: str | None) -> NegotiationSession:
    return NegotiationSession(
        task_id="task-1",
        provider="Comcast",
        phone_number="+15551234567",
        vertical="cable_internet",
        user_id=user_id,
    )


@pytest.fixture(autouse=True)
def _no_global_contacts(monkeypatch):
    monkeypatch.setattr(settings, "escalation_whatsapp_to", "")
    monkeypatch.setattr(settings, "escalation_email_to", "")


def _with_profile(monkeypatch, profile: UserProfile | None):
    async def fake_get_profile(user_id: str):
        return profile

    monkeypatch.setattr(notify.supabase_store, "get_profile", fake_get_profile)


class TestRecipients:
    def test_the_owners_own_contacts_are_used(self, monkeypatch):
        _with_profile(
            monkeypatch,
            UserProfile(
                id="user-1",
                escalation_whatsapp="+2347000000000",
                escalation_email="owner@example.com",
            ),
        )
        whatsapp, email = asyncio.run(notify._recipients(_session("user-1")))
        assert whatsapp == "+2347000000000"
        assert email == "owner@example.com"

    def test_two_users_are_reached_separately(self, monkeypatch):
        """The actual bug: one global address for everybody."""
        profiles = {
            "user-1": UserProfile(id="user-1", escalation_whatsapp="+111"),
            "user-2": UserProfile(id="user-2", escalation_whatsapp="+222"),
        }

        async def fake_get_profile(user_id: str):
            return profiles.get(user_id)

        monkeypatch.setattr(notify.supabase_store, "get_profile", fake_get_profile)

        first, _ = asyncio.run(notify._recipients(_session("user-1")))
        second, _ = asyncio.run(notify._recipients(_session("user-2")))
        assert (first, second) == ("+111", "+222")

    def test_the_account_email_is_used_when_no_alert_email_is_set(self, monkeypatch):
        _with_profile(monkeypatch, UserProfile(id="user-1", email="me@example.com"))
        _, email = asyncio.run(notify._recipients(_session("user-1")))
        assert email == "me@example.com"

    def test_a_user_with_no_contacts_gets_no_escalation(self, monkeypatch):
        _with_profile(monkeypatch, UserProfile(id="user-1"))
        assert asyncio.run(notify._recipients(_session("user-1"))) == (None, None)

    def test_the_environment_is_only_a_fallback(self, monkeypatch):
        """Kept for a single-user or local deployment that has no profiles."""
        monkeypatch.setattr(settings, "escalation_whatsapp_to", "+999")
        _with_profile(monkeypatch, None)
        whatsapp, _ = asyncio.run(notify._recipients(_session("user-1")))
        assert whatsapp == "+999"

    def test_a_profile_lookup_failure_never_breaks_the_call(self, monkeypatch):
        async def boom(user_id: str):
            raise RuntimeError("supabase is down")

        monkeypatch.setattr(notify.supabase_store, "get_profile", boom)
        assert asyncio.run(notify._recipients(_session("user-1"))) == (None, None)

    def test_an_unowned_session_falls_back_without_a_lookup(self, monkeypatch):
        async def boom(user_id: str):
            raise AssertionError("should not be called for an unowned session")

        monkeypatch.setattr(notify.supabase_store, "get_profile", boom)
        assert asyncio.run(notify._recipients(_session(None))) == (None, None)


class TestDelivery:
    def test_nothing_is_sent_when_the_user_has_no_contacts(self, monkeypatch):
        _with_profile(monkeypatch, UserProfile(id="user-1"))
        assert asyncio.run(notify.escalate(_session("user-1"), "needs a PIN")) == []

    def test_whatsapp_is_addressed_to_the_owner(self, monkeypatch):
        _with_profile(monkeypatch, UserProfile(id="user-1", escalation_whatsapp="+2347000000000"))
        monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
        monkeypatch.setattr(settings, "twilio_auth_token", "token")
        monkeypatch.setattr(settings, "twilio_whatsapp_from", "+15550000000")

        sent = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, auth=None, data=None, **kw):
                sent.update(data)
                return FakeResponse()

        monkeypatch.setattr(notify.httpx, "AsyncClient", lambda **kw: FakeClient())

        delivered = asyncio.run(notify.escalate(_session("user-1"), "needs a PIN"))
        assert delivered == ["WhatsApp"]
        assert sent["To"] == "whatsapp:+2347000000000"
