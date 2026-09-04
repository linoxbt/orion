"""The media stream URL must prove it came from a real call.

Twilio signs its HTTP webhooks but cannot sign a WebSocket upgrade, so
/telephony/stream previously accepted any connection quoting a task id:
enough to join a stranger's live call audio and open a billable session.
"""

import pytest

from app.config import settings
from app.services.twilio_client import (
    STREAM_TOKEN_TTL_SECONDS,
    TwilioNotConfigured,
    mint_stream_token,
    verify_stream_token,
)
from tests.conftest import ADMIN_KEY


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", ADMIN_KEY)


class TestStreamTokens:
    def test_a_minted_token_verifies(self):
        assert verify_stream_token("task-1", mint_stream_token("task-1")) is True

    def test_a_token_is_bound_to_one_task(self):
        """Otherwise a token from your own call opens someone else's."""
        assert verify_stream_token("task-2", mint_stream_token("task-1")) is False

    def test_a_missing_token_is_refused(self):
        assert verify_stream_token("task-1", None) is False
        assert verify_stream_token("task-1", "") is False

    def test_a_forged_digest_is_refused(self):
        token = mint_stream_token("task-1")
        expires, _, _ = token.partition(".")
        assert verify_stream_token("task-1", f"{expires}.{'0' * 64}") is False

    def test_a_malformed_token_is_refused_not_crashed(self):
        for bad in ("garbage", "abc.def", ".", "9999999999", "..."):
            assert verify_stream_token("task-1", bad) is False

    def test_an_expired_token_is_refused(self):
        import time

        past = time.time() - STREAM_TOKEN_TTL_SECONDS - 10
        assert verify_stream_token("task-1", mint_stream_token("task-1", now=past)) is False

    def test_extending_the_expiry_invalidates_the_signature(self):
        """The expiry is inside the signed payload, not merely alongside it."""
        token = mint_stream_token("task-1")
        _, _, digest = token.partition(".")
        import time

        assert verify_stream_token("task-1", f"{int(time.time()) + 9999}.{digest}") is False

    def test_an_unsigned_deployment_gets_no_stream_rather_than_an_open_one(
        self, monkeypatch
    ):
        token = mint_stream_token("task-1")
        monkeypatch.setattr(settings, "admin_api_key", "")
        assert verify_stream_token("task-1", token) is False
        with pytest.raises(TwilioNotConfigured):
            mint_stream_token("task-1")


class TestStreamEndpoint:
    @pytest.fixture
    def real_task(self, client) -> str:
        """A task id that genuinely exists.

        This matters: an unknown id was always refused, so a test using a made
        up one would pass with or without the fix and prove nothing. The hole
        was joining a *real* call.
        """
        return client.post(
            "/api/negotiations/start",
            headers={"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"},
            json={
                "provider": "VictimCorp",
                "phone_number": "+15550001111",
                "vertical": "cable_internet",
            },
        ).json()["task_id"]

    def test_a_connection_carrying_no_token_does_not_even_reach_the_route(
        self, client, real_task
    ):
        """The original hole, closed structurally.

        The token is a required path segment now, so a URL without one matches
        no route at all rather than reaching a handler that has to refuse it.
        The refusal is the same either way; this one just happens earlier."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/telephony/stream/{real_task}/") as ws:
                ws.receive_text()

    def test_a_connection_carrying_a_bad_token_is_refused_by_the_guard(
        self, client, real_task
    ):
        """A well-formed URL with a token that does not verify."""
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(
                f"/telephony/stream/{real_task}/1788500000.{'0' * 64}"
            ) as ws:
                ws.receive_text()
        assert caught.value.code == 1008

    def test_a_signed_connection_to_a_real_call_gets_past_the_token_check(
        self, client, real_task
    ):
        """The gate must not be closed to Twilio itself - a stream that always
        refuses would mean no call ever works."""
        from app.routers import telephony

        seen = {}

        async def fake_bridge(websocket, session):
            seen["task_id"] = session.task_id
            await websocket.accept()
            await websocket.close()

        original = telephony.run_bridge
        telephony.run_bridge = fake_bridge
        try:
            token = mint_stream_token(real_task)
            with client.websocket_connect(
                f"/telephony/stream/{real_task}/{token}"
            ):
                pass
        finally:
            telephony.run_bridge = original

        assert seen["task_id"] == real_task

    def test_the_websocket_refuses_a_token_minted_for_another_call(self, client):
        from starlette.websockets import WebSocketDisconnect

        other = mint_stream_token("someone-elses-call")
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(f"/telephony/stream/mine/{other}") as ws:
                ws.receive_text()
        assert caught.value.code == 1008
