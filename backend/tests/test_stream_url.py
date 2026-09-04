"""The Media Stream URL, as Twilio actually receives it.

Every real call dropped the instant it was answered. The stream URL carried
two query parameters, so it needed an "&", the TwiML serialiser escaped that
to "&amp;", and Twilio passed it through verbatim - so the token arrived under
the name "amp;token", this server saw no token, refused the socket, and since
<Connect> is a terminal verb Twilio hung up.

The earlier tests missed it because they built the URL themselves, or
un-escaped the XML by hand before connecting. These parse the URL out of the
TwiML the way a client must, which is the only form that proves anything.
"""

import re
from xml.etree import ElementTree

import pytest
from twilio.request_validator import RequestValidator

from app.config import settings
from app.services.twilio_client import stream_websocket_url, voice_webhook_url
from tests.conftest import ADMIN_HEADERS


def _twiml(client, task_id: str) -> str:
    url = voice_webhook_url(task_id)
    params = {"CallSid": "CA" + "0" * 32, "CallStatus": "in-progress"}
    sig = RequestValidator(settings.twilio_auth_token).compute_signature(url, params)
    res = client.post(
        "/telephony/voice",
        params={"taskId": task_id},
        data=params,
        headers={"X-Twilio-Signature": sig},
    )
    assert res.status_code == 200, res.text
    return res.text


@pytest.fixture(autouse=True)
def _twilio(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "test-auth-token")


class TestNoAmpersand:
    """The bug class, closed at the source."""

    def test_the_stream_url_has_no_query_string_at_all(self):
        url = stream_websocket_url("11111111-1111-1111-1111-111111111111")
        assert "?" not in url
        assert "&" not in url

    def test_the_task_id_and_token_are_path_segments(self):
        task = "11111111-1111-1111-1111-111111111111"
        url = stream_websocket_url(task)
        tail = url.split("/telephony/stream/", 1)[1]
        segments = tail.split("/")
        assert segments[0] == task
        assert len(segments) == 2 and segments[1]

    def test_the_twiml_contains_no_escaped_ampersand(self, client):
        """&amp; in the URL is the exact string Twilio passed through
        literally, which is what broke every call."""
        body = _twiml(client, "11111111-1111-1111-1111-111111111111")
        assert "&amp;" not in body
        assert "&" not in body


class TestAsTwilioParsesIt:
    """Drive the URL taken out of the XML, never one built by hand."""

    def _stream_url(self, client, task_id: str) -> str:
        body = _twiml(client, task_id)
        # An XML parser is what Twilio uses, so use one here too rather than
        # a string replace that could hide an escaping problem.
        root = ElementTree.fromstring(body)
        stream = root.find("./Connect/Stream")
        assert stream is not None
        return stream.attrib["url"]

    def test_the_parsed_url_still_carries_the_token(self, client):
        task = "11111111-1111-1111-1111-111111111111"
        url = self._stream_url(client, task)
        assert re.search(rf"/telephony/stream/{task}/\d+\.[0-9a-f]{{64}}$", url)

    def test_the_parsed_url_opens_the_stream(self, client, monkeypatch):
        """The whole bug in one assertion: this refused before."""
        from app.routers import telephony

        task = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567",
                  "vertical": "cable_internet"},
        ).json()["task_id"]

        seen = {}

        async def fake_bridge(websocket, session):
            seen["task_id"] = session.task_id
            await websocket.accept()
            await websocket.close()

        monkeypatch.setattr(telephony, "run_bridge", fake_bridge)

        url = self._stream_url(client, task)
        path = url.split("backend", 1)[-1]
        path = url[url.index("/telephony/stream/"):]

        with client.websocket_connect(path):
            pass
        assert seen["task_id"] == task

    def test_a_tampered_token_is_still_refused(self, client):
        from starlette.websockets import WebSocketDisconnect

        task = "11111111-1111-1111-1111-111111111111"
        url = self._stream_url(client, task)
        path = url[url.index("/telephony/stream/"):]
        broken = path.rsplit(".", 1)[0] + "." + "0" * 64

        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(broken) as ws:
                ws.receive_text()
        assert caught.value.code == 1008
