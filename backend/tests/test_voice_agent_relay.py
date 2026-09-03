"""Relay lifecycle tests, driven by a scripted fake Voice Agent session.

Everything here is the class of bug that never shows up until a real call is in
progress and then shows up as silence, a click, or an agent answering a question
the human already talked over. None of it needs a phone, a Twilio number, or a
billable AssemblyAI session.
"""

import asyncio
import base64
import json

import pytest

from app.config import settings
from app.services import voice_agent
from app.services.voice_agent import VoiceAgentRelay


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    """The relay builds its auth header before connecting; conftest blanks every
    real credential, so give it a placeholder. Nothing here reaches the network."""
    monkeypatch.setattr(settings, "assemblyai_api_key", "test-key")

MULAW_FRAME = base64.b64encode(b"\xff" * 160).decode("ascii")
AGENT_AUDIO = base64.b64encode(b"\x7f" * 160).decode("ascii")


class FakeTwilio:
    """Stands in for the Twilio Media Stream websocket.

    `gate`, when set, is awaited before any media event is delivered. Twilio
    supplies audio continuously in a real call, so without it this fake drains
    its whole script before the agent pump has processed session.ready - which
    is a property of the fake, not of the relay.
    """

    def __init__(self, inbound: list[dict], gate: asyncio.Event | None = None):
        self._inbound = list(inbound)
        self.sent: list[dict] = []
        self.gate = gate

    async def receive_text(self) -> str:
        if not self._inbound:
            # Nothing left to say; behave like a caller who hung up.
            return json.dumps({"event": "stop"})
        if self._inbound[0].get("event") == "media" and self.gate is not None:
            await self.gate.wait()
        return json.dumps(self._inbound.pop(0))

    async def send_text(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def events(self, kind: str) -> list[dict]:
        return [event for event in self.sent if event.get("event") == kind]


class FakeAgent:
    """Stands in for the AssemblyAI Voice Agent websocket."""

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def __aiter__(self):
        async def messages():
            for message in self._script:
                # Let the Twilio pump run between agent messages.
                await asyncio.sleep(0)
                yield json.dumps(message)

        return messages()

    def messages(self, kind: str) -> list[dict]:
        return [message for message in self.sent if message.get("type") == kind]


def run_relay(relay: VoiceAgentRelay, agent: FakeAgent) -> None:
    class Connection:
        async def __aenter__(self):
            return agent

        async def __aexit__(self, *_):
            return False

    def fake_connect(*_args, **_kwargs):
        return Connection()

    original = voice_agent.ws_connect
    voice_agent.ws_connect = fake_connect
    try:
        asyncio.run(asyncio.wait_for(relay.run(), timeout=5))
    finally:
        voice_agent.ws_connect = original


class Recording(VoiceAgentRelay):
    """A relay with a fixed config that records what its hooks saw."""

    def __init__(self, websocket, tool_result: str = "done"):
        super().__init__(websocket, label="test")
        self.ready_gate = getattr(websocket, "gate", None)
        self.transcripts: list[tuple[str, str]] = []
        self.tool_calls: list[tuple[str, dict]] = []
        self.interruptions = 0
        self.started: list[dict] = []
        self._tool_result = tool_result

    def session_config(self):
        return {"system_prompt": "test", "input": {}, "output": {}}

    async def on_ready(self):
        if self.ready_gate is not None:
            self.ready_gate.set()

    async def on_start(self, start_event):
        self.started.append(start_event)

    async def on_transcript(self, speaker, text):
        self.transcripts.append((speaker, text))

    async def on_tool_call(self, name, arguments):
        self.tool_calls.append((name, arguments))
        return self._tool_result

    async def on_interrupted(self):
        self.interruptions += 1


START = {"event": "start", "start": {"streamSid": "MZ123", "callSid": "CA456"}}


def test_audio_is_relayed_untranscoded_in_both_directions():
    """Twilio's base64 mu-law goes out as-is and comes back as-is - any
    difference means something resampled it."""
    gate = asyncio.Event()
    twilio = FakeTwilio(
        [START, {"event": "media", "media": {"payload": MULAW_FRAME}}, {"event": "stop"}], gate=gate
    )
    agent = FakeAgent([{"type": "session.ready"}, {"type": "reply.audio", "data": AGENT_AUDIO}])
    relay = Recording(twilio)

    run_relay(relay, agent)

    inbound = agent.messages("input.audio")
    assert inbound and inbound[0]["audio"] == MULAW_FRAME
    outbound = twilio.events("media")
    assert outbound and outbound[0]["media"]["payload"] == AGENT_AUDIO
    assert outbound[0]["streamSid"] == "MZ123"


def test_audio_before_session_ready_is_dropped():
    """Audio sent before the agent session is live is discarded, not queued."""
    twilio = FakeTwilio([START, {"event": "media", "media": {"payload": MULAW_FRAME}}, {"event": "stop"}])
    agent = FakeAgent([])  # session.ready never arrives
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert agent.messages("input.audio") == []


def test_session_update_is_sent_immediately():
    """Configuration goes up front - waiting for session.ready would deadlock."""
    twilio = FakeTwilio([{"event": "stop"}])
    agent = FakeAgent([])
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert agent.sent[0]["type"] == "session.update"
    assert agent.sent[0]["session"]["system_prompt"] == "test"


def test_barge_in_clears_the_twilio_buffer():
    """Twilio buffers ahead, so an interrupted reply keeps playing unless the
    buffer is explicitly flushed."""
    twilio = FakeTwilio([START, {"event": "stop"}])
    agent = FakeAgent(
        [
            {"type": "session.ready"},
            {"type": "reply.audio", "data": AGENT_AUDIO},
            {"type": "reply.done", "status": "interrupted"},
        ]
    )
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert twilio.events("clear")
    assert relay.interruptions == 1


def test_tool_results_are_held_until_the_turn_completes():
    twilio = FakeTwilio([START, {"event": "stop"}])
    agent = FakeAgent(
        [
            {"type": "session.ready"},
            {"type": "tool.call", "call_id": "c1", "name": "log_offer", "arguments": {"monthly_rate": 85}},
            {"type": "reply.done", "status": "completed"},
        ]
    )
    relay = Recording(twilio, tool_result="Offer logged.")

    run_relay(relay, agent)

    assert relay.tool_calls == [("log_offer", {"monthly_rate": 85})]
    results = agent.messages("tool.result")
    assert len(results) == 1
    assert results[0]["call_id"] == "c1"
    assert results[0]["result"] == "Offer logged."


def test_tool_results_are_discarded_on_barge_in():
    """The human talked over the answer - sending it now answers a question
    that is no longer on the table."""
    twilio = FakeTwilio([START, {"event": "stop"}])
    agent = FakeAgent(
        [
            {"type": "session.ready"},
            {"type": "tool.call", "call_id": "c1", "name": "log_offer", "arguments": {}},
            {"type": "reply.done", "status": "interrupted"},
        ]
    )
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert relay.tool_calls  # the tool still ran
    assert agent.messages("tool.result") == []  # but its answer was dropped


def test_transcripts_are_labelled_by_side():
    twilio = FakeTwilio([START, {"event": "stop"}])
    agent = FakeAgent(
        [
            {"type": "session.ready"},
            {"type": "transcript.user", "transcript": "Thanks for calling."},
            {"type": "transcript.agent", "transcript": "I'd like to lower this bill."},
            {"type": "transcript.user", "transcript": "   "},
        ]
    )
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert relay.transcripts == [
        ("them", "Thanks for calling."),
        ("us", "I'd like to lower this bill."),
    ]


def test_call_sid_is_captured_from_the_start_event():
    twilio = FakeTwilio([START, {"event": "stop"}])
    agent = FakeAgent([{"type": "session.ready"}])
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert relay.started[0]["callSid"] == "CA456"
    assert relay.stream_sid == "MZ123"


def test_media_before_start_is_not_sent_to_twilio():
    """Without a streamSid there is nowhere to send audio; it must not crash."""
    twilio = FakeTwilio([{"event": "stop"}])
    agent = FakeAgent([{"type": "session.ready"}, {"type": "reply.audio", "data": AGENT_AUDIO}])
    relay = Recording(twilio)

    run_relay(relay, agent)

    assert twilio.events("media") == []
