import pytest
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from app.config import settings
from app.services.twilio_client import mint_stream_token
from tests.conftest import ADMIN_HEADERS


def _signed_headers(url: str, params: dict[str, str] | None = None) -> dict[str, str]:
    validator = RequestValidator(settings.twilio_auth_token)
    return {"X-Twilio-Signature": validator.compute_signature(url, params or {})}


def test_voice_webhook_returns_503_when_twilio_not_configured(client):
    res = client.post("/telephony/voice", params={"taskId": "abc-123"})
    assert res.status_code == 503
    assert res.json()["detail"] == "twilio_not_configured"


def test_voice_webhook_rejects_missing_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "test-auth-token")
    res = client.post("/telephony/voice", params={"taskId": "abc-123"})
    assert res.status_code == 403
    assert res.json()["detail"] == "invalid_twilio_signature"


def test_voice_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "test-auth-token")
    res = client.post(
        "/telephony/voice", params={"taskId": "abc-123"}, headers={"X-Twilio-Signature": "not-a-real-signature"}
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "invalid_twilio_signature"


def test_voice_webhook_returns_twiml_stream_pointing_at_websocket(client, monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "test-auth-token")
    url = f"{settings.base_url}/telephony/voice?taskId=abc-123"

    res = client.post("/telephony/voice", params={"taskId": "abc-123"}, headers=_signed_headers(url))
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    body = res.text
    assert "<Connect>" in body
    assert "/telephony/stream/abc-123/" in body
    # Path segments, not a query string: an "&" here is escaped to "&amp;"
    # in the XML and passed through literally by Twilio, which is what
    # silently refused every real call.
    assert "&" not in body
    assert "wss://" in body or "ws://" in body


def test_stream_closes_for_unknown_task_id(client):
    # The server closes with 1008 before accepting, which the test client
    # surfaces as WebSocketDisconnect on connect rather than a clean close.
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/telephony/stream/does-not-exist/{mint_stream_token('does-not-exist')}"):
            pass
    assert exc_info.value.code == 1008


def test_stream_closes_assemblyai_not_configured_for_known_task(client):
    start = client.post(
        "/api/negotiations/start",
        headers=ADMIN_HEADERS,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    )
    assert start.status_code == 200  # /start only creates the session, doesn't call Twilio
    task_id = start.json()["task_id"]

    # AssemblyAI isn't configured either, so the bridge should accept then
    # immediately close rather than hang or crash.
    token = mint_stream_token(task_id)
    with client.websocket_connect(
        f"/telephony/stream/{task_id}/{token}"
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_text()
    assert exc_info.value.code == 1011
    assert exc_info.value.reason == "assemblyai_not_configured"
