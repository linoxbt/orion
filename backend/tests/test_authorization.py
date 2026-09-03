"""Nobody may touch a negotiation that isn't theirs.

Every one of these was reproduced against production before the fix: with any
valid session, knowing a task id was enough to read someone else's
negotiation, write a security PIN onto it, consent on their behalf, and reach
the call endpoint. Only the list endpoint was scoped.
"""

import pytest

from app.config import settings
from tests.conftest import ADMIN_KEY

OWNER = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}
INTRUDER = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "intruder"}


@pytest.fixture
def owned(client) -> str:
    return client.post(
        "/api/negotiations/start",
        headers=OWNER,
        json={"provider": "VictimCorp", "phone_number": "+15550001111", "vertical": "cable_internet"},
    ).json()["task_id"]


class TestCrossUserReads:
    def test_cannot_read_another_users_negotiation(self, client, owned):
        assert client.get(f"/api/negotiations/{owned}", headers=INTRUDER).status_code == 404

    def test_the_owner_still_can(self, client, owned):
        res = client.get(f"/api/negotiations/{owned}", headers=OWNER)
        assert res.status_code == 200
        assert res.json()["provider"] == "VictimCorp"

    def test_a_stranger_gets_the_same_answer_as_a_missing_id(self, client, owned):
        """404 rather than 403, so the response doesn't confirm the id exists."""
        theirs = client.get(f"/api/negotiations/{owned}", headers=INTRUDER)
        missing = client.get("/api/negotiations/does-not-exist", headers=INTRUDER)
        assert theirs.status_code == missing.status_code == 404
        assert theirs.json() == missing.json()

    def test_cannot_list_account_detail_fields(self, client, owned):
        assert (
            client.get(f"/api/negotiations/{owned}/account-details", headers=INTRUDER).status_code
            == 404
        )

    def test_cannot_open_the_live_event_feed(self, client, owned):
        assert client.get(f"/api/negotiations/{owned}/events", headers=INTRUDER).status_code == 404


class TestCrossUserWrites:
    def test_cannot_write_verification_details(self, client, owned):
        """This wrote a security PIN onto a stranger's negotiation."""
        res = client.post(
            f"/api/negotiations/{owned}/account-details",
            headers=INTRUDER,
            json={"security_pin": "9999"},
        )
        assert res.status_code == 404

    def test_cannot_consent_on_someone_elses_behalf(self, client, owned):
        """The worst of them: it manufactured a legal record that someone
        authorised representation they never agreed to."""
        res = client.post(
            f"/api/negotiations/{owned}/consent",
            headers=INTRUDER,
            json={"signer_name": "Intruder", "agreed": True},
        )
        assert res.status_code == 404

        # And the negotiation is untouched.
        session = client.get(f"/api/negotiations/{owned}", headers=OWNER).json()
        assert session["authorized"] is False
        assert session["consent_signer_name"] is None

    def test_cannot_place_a_call(self, client, owned):
        """With Twilio configured this dialled a real number on someone else's
        negotiation."""
        res = client.post(f"/api/negotiations/{owned}/call", headers=INTRUDER)
        assert res.status_code == 404

    def test_cannot_record_an_outcome(self, client, owned):
        res = client.post(
            f"/api/negotiations/{owned}/complete",
            headers=INTRUDER,
            json={"outcome": "forged", "previous_rate": 100.0, "new_rate": 1.0},
        )
        assert res.status_code == 404

    def test_cannot_charge_someone_elses_card(self, client, owned):
        assert client.post(f"/api/negotiations/{owned}/charge", headers=INTRUDER).status_code == 404


class TestBrowserAgentScoping:
    def test_cannot_mint_a_session_for_another_users_negotiation(self, client, owned):
        """Minting is billable, and the config carries their system prompt."""
        assert (
            client.post(f"/api/browser/{owned}/session", headers=INTRUDER).status_code == 404
        )

    def test_cannot_run_tools_on_another_users_negotiation(self, client, owned):
        res = client.post(
            f"/api/browser/{owned}/tool",
            headers=INTRUDER,
            json={"name": "log_offer", "arguments": {"description": "forged"}},
        )
        assert res.status_code == 404

    def test_cannot_inject_transcript_turns(self, client, owned):
        res = client.post(
            f"/api/browser/{owned}/transcript",
            headers=INTRUDER,
            json={"speaker": "rep", "text": "forged turn"},
        )
        assert res.status_code == 404


class TestRenewalsScoping:
    def test_renewals_only_lists_the_callers_own(self, client):
        """This listed other people's providers and renewal dates to anyone
        signed in."""
        from datetime import date, timedelta

        soon = (date.today() + timedelta(days=10)).isoformat()
        client.post(
            "/api/negotiations/start",
            headers=OWNER,
            json={
                "provider": "OwnerCorp",
                "phone_number": "+15550001111",
                "vertical": "cable_internet",
                "bill": {"provider": "OwnerCorp", "contract_end_date": soon},
            },
        )

        theirs = client.get("/api/renewals", headers=INTRUDER).json()
        assert all(r["provider"] != "OwnerCorp" for r in theirs)

        mine = client.get("/api/renewals", headers=OWNER).json()
        assert any(r["provider"] == "OwnerCorp" for r in mine)


class TestSessionVerification:
    def test_an_unverified_header_is_refused_once_dynamic_is_configured(
        self, client, monkeypatch
    ):
        """The admin key used to be a universal impersonation token: anything
        holding it could claim to be anyone. With Dynamic configured, only a
        signed session token counts."""
        monkeypatch.setattr(settings, "dynamic_environment_id", "some-environment")
        res = client.get("/api/negotiations", headers=OWNER)
        assert res.status_code == 401
        assert res.json()["detail"] == "no_verified_session"

    def test_a_forged_bearer_token_is_refused(self, client, monkeypatch):
        monkeypatch.setattr(settings, "dynamic_environment_id", "some-environment")
        res = client.get(
            "/api/negotiations",
            headers={**OWNER, "Authorization": "Bearer not.a.real.jwt"},
        )
        assert res.status_code == 401

    def test_the_admin_key_alone_is_still_not_an_identity(self, client):
        res = client.get("/api/negotiations", headers={"X-Orion-Admin-Key": ADMIN_KEY})
        assert res.status_code == 401


class TestRateLimits:
    """Two endpoints spend real money per call and had no limit at all: bill
    extraction burns Gemini quota, and minting an agent session opens a
    billable AssemblyAI session."""

    def setup_method(self):
        from app.services.ratelimit import reset

        reset()

    def teardown_method(self):
        from app.services.ratelimit import reset

        reset()

    def test_extraction_is_capped_per_user(self, client):
        files = {"file": ("bill.pdf", b"%PDF-1.4", "application/pdf")}
        seen = set()
        for _ in range(25):
            seen.add(client.post("/api/bills/ingest", headers=OWNER, files=files).status_code)
        assert 429 in seen

    def test_the_cap_is_per_user_not_global(self, client):
        """One noisy account must not lock everyone else out."""
        files = {"file": ("bill.pdf", b"%PDF-1.4", "application/pdf")}
        for _ in range(25):
            client.post("/api/bills/ingest", headers=OWNER, files=files)

        # A different user is unaffected - 503 is the honest "Gemini unset".
        other = client.post("/api/bills/ingest", headers=INTRUDER, files=files)
        assert other.status_code != 429

    def test_a_limited_response_says_when_to_retry(self, client):
        files = {"file": ("bill.pdf", b"%PDF-1.4", "application/pdf")}
        last = None
        for _ in range(25):
            last = client.post("/api/bills/ingest", headers=OWNER, files=files)
        assert last.status_code == 429
        assert "Retry-After" in last.headers


class TestEventRetention:
    """Replay buffers used to be kept for every negotiation the process ever
    saw, for the life of the process - a permanent memory climb."""

    def test_buffers_are_evicted_once_a_call_is_old_and_unwatched(self, monkeypatch):
        from app.services import events

        events._replay.clear()
        events._last_seen.clear()

        events.publish("old-call", {"type": "status", "status": "call_ended"})
        assert events.tracked_calls() == 1

        # Age it past the TTL.
        events._last_seen["old-call"] -= events.REPLAY_TTL_SECONDS + 1
        events.publish("new-call", {"type": "status", "status": "connected"})

        assert "old-call" not in events._replay
        assert "new-call" in events._replay

    def test_a_watched_call_is_never_evicted(self):
        """Evicting a call somebody is still listening to would silently empty
        a live transcript."""
        import asyncio

        from app.services import events

        events._replay.clear()
        events._last_seen.clear()

        events.publish("live-call", {"type": "turn", "speaker": "rep", "text": "hello"})
        events._subscribers["live-call"].add(asyncio.Queue())
        events._last_seen["live-call"] -= events.REPLAY_TTL_SECONDS + 1

        events.publish("other", {"type": "status", "status": "connected"})

        assert "live-call" in events._replay
        events._subscribers.pop("live-call", None)
        events._replay.clear()
        events._last_seen.clear()

    def test_a_hard_ceiling_caps_total_buffers(self):
        from app.services import events

        events._replay.clear()
        events._last_seen.clear()
        for i in range(events.MAX_TRACKED_CALLS + 50):
            events.publish(f"call-{i}", {"type": "status", "status": "connected"})

        assert events.tracked_calls() <= events.MAX_TRACKED_CALLS
        events._replay.clear()
        events._last_seen.clear()


class TestPagination:
    def test_listing_is_bounded(self, client):
        """An unbounded list is a slow page and a growing payload."""
        for i in range(5):
            client.post(
                "/api/negotiations/start",
                headers=OWNER,
                json={
                    "provider": f"Provider{i}",
                    "phone_number": "+15550001111",
                    "vertical": "cable_internet",
                },
            )
        from app.store import list_sessions
        import asyncio

        page = asyncio.run(list_sessions("owner", limit=2))
        assert len(page) == 2


class TestJwksFetching:
    """Dynamic's edge answers 403 to PyJWKClient's default urllib User-Agent.

    Caught only by exercising the real endpoint: every unit test passed while
    production would have rejected every signed-in user with a 401. The failure
    is total and silent, so it is worth pinning.
    """

    def setup_method(self):
        from app import security

        security._jwks_client = None

    def teardown_method(self):
        from app import security

        security._jwks_client = None

    def test_the_key_client_sends_a_user_agent(self, monkeypatch):
        from app import security

        monkeypatch.setattr(settings, "dynamic_environment_id", "env-123")
        captured = {}

        class FakeClient:
            def __init__(self, uri, **kwargs):
                captured["uri"] = uri
                captured.update(kwargs)

        monkeypatch.setattr(security, "PyJWKClient", FakeClient)
        security._jwks()

        assert "User-Agent" in captured["headers"]
        assert captured["headers"]["User-Agent"]
        assert "env-123" in captured["uri"]

    def test_an_unreachable_jwks_is_reported_not_swallowed(self, monkeypatch, caplog):
        import asyncio
        import logging

        from app import security

        monkeypatch.setattr(settings, "dynamic_environment_id", "env-123")

        class Broken:
            def __init__(self, *a, **k):
                pass

            def get_jwk_set(self):
                raise RuntimeError("HTTP Error 403: Forbidden")

        monkeypatch.setattr(security, "PyJWKClient", Broken)
        with caplog.at_level(logging.ERROR):
            assert asyncio.run(security.check_jwks_reachable()) is False
        assert "UNREACHABLE" in caplog.text

    def test_a_missing_environment_id_is_warned_about(self, monkeypatch, caplog):
        import asyncio
        import logging

        from app import security

        monkeypatch.setattr(settings, "dynamic_environment_id", "")
        with caplog.at_level(logging.WARNING):
            assert asyncio.run(security.check_jwks_reachable()) is False
        assert "DYNAMIC_ENVIRONMENT_ID" in caplog.text


class TestUnownedSessions:
    """A session with no owner used to be readable by every signed-in user.

    The code called this "claimed by the first caller", but nothing ever wrote
    an owner, so it was a permanent shared-access hole rather than a one-time
    claim.
    """

    def test_an_unowned_session_is_not_readable_by_anyone(self, client):
        import asyncio

        from app.store import get_session, save_session

        task_id = client.post(
            "/api/negotiations/start",
            headers=OWNER,
            json={
                "provider": "LegacyCorp",
                "phone_number": "+15550001111",
                "vertical": "cable_internet",
            },
        ).json()["task_id"]

        # Strip the owner, reproducing a row created before ownership existed.
        session = asyncio.run(get_session(task_id))
        session.user_id = None
        asyncio.run(save_session(session))

        assert client.get(f"/api/negotiations/{task_id}", headers=OWNER).status_code == 404
        assert client.get(f"/api/negotiations/{task_id}", headers=INTRUDER).status_code == 404
        assert (
            client.post(f"/api/negotiations/{task_id}/call", headers=INTRUDER).status_code == 404
        )
