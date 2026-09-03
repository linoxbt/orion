"""Tests for the AssemblyAI voice layer: session config, tools, and verification.

These cover the parts that are wrong-by-construction rather than wrong-at-runtime -
the audio encodings, the tool schema shape, the streaming query string, and the
redaction policy set. Those are exactly the mistakes that only show up as a
silent failure on a live phone call, so they're pinned here instead.
"""

import asyncio
import json

import pytest

from app.models import NegotiationSession
from app.services import call_tools, prompting, tts, verification
from app.services.agent_bridge import session_update
from app.services.negotiation_llm import (
    _gateway_tools,
    _portable,
    assistant_message,
    LLMReply,
    ToolCall,
)
from app.services.stt_bridge import _streaming_url


@pytest.fixture
def session() -> NegotiationSession:
    return NegotiationSession(
        task_id="task-1", provider="Comcast", phone_number="+15551234567", vertical="cable_internet"
    )


class TestVoiceAgentSessionConfig:
    def test_input_and_output_are_both_mulaw(self, session):
        """Setting only the input leaves the agent replying in 24kHz PCM that
        Twilio can't play - the single most common bug in this integration."""
        config = session_update(session)["session"]
        assert config["input"]["format"]["encoding"] == "audio/pcmu"
        assert config["output"]["format"]["encoding"] == "audio/pcmu"

    def test_tools_use_the_flat_schema(self, session):
        """The Voice Agent API takes {type, name, parameters}, not OpenAI's
        nested {type:"function", function:{...}}."""
        for tool in session_update(session)["session"]["tools"]:
            assert tool["type"] == "function"
            assert isinstance(tool["name"], str)
            assert "function" not in tool
            assert tool["parameters"]["type"] == "object"

    def test_prompt_carries_the_provider_and_ai_disclosure(self, session):
        config = session_update(session)["session"]
        assert "Comcast" in config["system_prompt"]
        assert "AI representative" in config["system_prompt"]
        # The person answering has no idea why they were called.
        assert config["greeting"]


class TestStreamingUrl:
    def test_uses_singular_speech_model_at_native_phone_format(self, session):
        url = _streaming_url(session)
        # Singular string on realtime; the plural array is pre-recorded only.
        assert "speech_model=universal-3-5-pro" in url
        assert "speech_models" not in url
        # Phone audio stays at 8kHz mu-law - upsampling costs accuracy.
        assert "encoding=pcm_mulaw" in url
        assert "sample_rate=8000" in url

    def test_omits_parameters_universal_3_5_pro_ignores(self, session):
        url = _streaming_url(session)
        assert "format_turns" not in url
        assert "end_of_turn_confidence_threshold" not in url



class TestKeyterms:
    def test_includes_provider_and_is_deduplicated(self, session):
        terms = prompting.keyterms(session)
        assert "Comcast" in terms
        assert len(terms) == len({term.lower() for term in terms})

    def test_respects_the_realtime_cap(self, session):
        assert len(prompting.keyterms(session)) <= prompting.KEYTERM_LIMIT


def _dispatch(session, name, arguments):
    from app.store import init_db

    async def run():
        await init_db()
        return await call_tools.dispatch(session, name, arguments)

    return asyncio.run(run())


class TestCallTools:
    def test_log_offer_appends_to_the_session(self, session, isolated_db):
        result = _dispatch(
            session, "log_offer", {"monthly_rate": 49.99, "description": "12mo promo", "accepted": True}
        )
        assert "logged" in result.lower()
        assert session.offers[0].monthly_rate == 49.99
        assert session.offers[0].accepted is True

    def test_record_confirmation_number_sets_the_rate(self, session, isolated_db):
        _dispatch(
            session,
            "record_confirmation_number",
            {"confirmation_number": "CMC-88421", "new_monthly_rate": 49.99},
        )
        assert session.confirmation_number == "CMC-88421"
        assert session.new_rate == 49.99

    def test_escalation_is_recorded(self, session, isolated_db):
        _dispatch(session, "escalate_to_human", {"reason": "Rep refused to transfer"})
        assert session.escalated is True
        assert session.escalation_reason == "Rep refused to transfer"

    def test_unknown_tool_does_not_raise(self, session, isolated_db):
        """An unrecognised tool call must not tear down a live phone call."""
        result = _dispatch(session, "not_a_real_tool", {})
        assert "Unknown tool" in result


class TestRedactionPolicies:
    def test_does_not_redact_what_the_product_needs(self):
        """Redacting money amounts or number sequences would erase the
        negotiated rate and the confirmation number - the entire outcome."""
        assert "money_amount" not in verification.REDACT_POLICIES
        assert "number_sequence" not in verification.REDACT_POLICIES

    def test_redacts_the_sensitive_identifiers(self):
        for policy in ("account_number", "credit_card_number", "us_social_security_number"):
            assert policy in verification.REDACT_POLICIES


class TestWavHeaderStripping:
    def test_strips_a_riff_container(self):
        payload = b"\xff" * 32
        wav = (
            b"RIFF" + (36 + len(payload)).to_bytes(4, "little") + b"WAVE"
            + b"fmt " + (16).to_bytes(4, "little") + b"\x00" * 16
            + b"data" + len(payload).to_bytes(4, "little") + payload
        )
        assert tts._strip_wav_header(wav) == payload

    def test_passes_bare_audio_through(self):
        raw = b"\x7f" * 100
        assert tts._strip_wav_header(raw) == raw


class TestTranscriptDialogue:
    def test_prefers_speaker_labelled_utterances(self):
        dialogue = verification._dialogue(
            {
                "text": "flat text",
                "utterances": [
                    {"speaker": "A", "text": "Thanks for calling."},
                    {"speaker": "B", "text": "I'd like to lower this bill."},
                ],
            }
        )
        assert "Speaker A: Thanks for calling." in dialogue
        assert "Speaker B: I'd like to lower this bill." in dialogue

    def test_falls_back_to_flat_text(self):
        assert verification._dialogue({"text": "flat text", "utterances": []}) == "flat text"


class TestTranscriptWebhook:
    def test_rejects_a_request_without_the_auth_header(self, client):
        res = client.post("/telephony/transcript", params={"taskId": "abc"}, json={"status": "completed"})
        assert res.status_code == 403
        assert res.json()["detail"] == "invalid_webhook_auth"

    def test_rejects_a_wrong_auth_header(self, client):
        res = client.post(
            "/telephony/transcript",
            params={"taskId": "abc"},
            headers={"X-Orion-Admin-Key": "not-the-key"},
            json={"status": "completed"},
        )
        assert res.status_code == 403

    def test_ignores_a_non_completed_status(self, client):
        from tests.conftest import ADMIN_HEADERS

        start = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        )
        task_id = start.json()["task_id"]

        res = client.post(
            f"/telephony/transcript?taskId={task_id}",
            headers=ADMIN_HEADERS,
            json={"transcript_id": "t-1", "status": "processing"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"


class TestRecordingWebhook:
    def test_returns_503_when_twilio_not_configured(self, client):
        res = client.post("/telephony/recording", params={"taskId": "abc"})
        assert res.status_code == 503
        assert res.json()["detail"] == "twilio_not_configured"


class TestEventStream:
    def test_unknown_task_returns_404(self, client):
        from tests.conftest import ADMIN_HEADERS

        res = client.get("/api/negotiations/does-not-exist/events", headers=ADMIN_HEADERS)
        assert res.status_code == 404

    def test_buffers_events_for_a_late_subscriber(self):
        """A browser landing mid-call must still render the turns it missed."""
        from app.services import events

        events.clear("task-replay")
        events.publish("task-replay", {"type": "turn", "speaker": "rep", "text": "Thanks for calling."})
        events.publish("task-replay", {"type": "offer", "monthly_rate": 49.99})

        buffered = events.history("task-replay")
        assert [event["type"] for event in buffered] == ["turn", "offer"]
        assert json.loads(json.dumps(buffered[0]))["text"] == "Thanks for calling."
        events.clear("task-replay")

    def test_publish_survives_a_task_with_no_subscribers(self):
        from app.services import events

        events.clear("nobody-listening")
        events.publish("nobody-listening", {"type": "status", "status": "connected"})
        assert len(events.history("nobody-listening")) == 1
        events.clear("nobody-listening")


class TestNegotiationLLM:
    def test_gateway_tool_wrapping_is_nested(self):
        """LLM Gateway is OpenAI-compatible, so the same tools need the nested
        form there - the opposite of the Voice Agent API's flat schema."""
        for tool in _gateway_tools(call_tools.TOOL_DEFINITIONS):
            assert tool["type"] == "function"
            assert set(tool["function"]) == {"name", "description", "parameters"}

    def test_assistant_message_round_trips_tool_calls(self):
        """Whichever provider answered, the history stays OpenAI-shaped so the
        other provider can pick the conversation up mid-call."""
        reply = LLMReply(
            content="Let me check that.",
            tool_calls=[ToolCall(id="call_0_log_offer", name="log_offer", arguments={"monthly_rate": 49.99})],
        )
        message = assistant_message(reply)
        assert message["role"] == "assistant"
        assert message["tool_calls"][0]["function"]["name"] == "log_offer"
        assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"monthly_rate": 49.99}

    def test_assistant_message_omits_tool_calls_when_there_are_none(self):
        assert "tool_calls" not in assistant_message(LLMReply(content="Thanks."))

    def test_unknown_provider_is_rejected(self, monkeypatch):
        import asyncio as _asyncio

        from app.config import settings
        from app.services.negotiation_llm import UnknownNegotiationLLM, complete

        monkeypatch.setattr(settings, "negotiation_llm", "not-a-provider")
        with pytest.raises(UnknownNegotiationLLM):
            _asyncio.run(complete([], []))

    def test_gemini_contents_split_system_out_of_band(self):
        """Gemini takes the system prompt separately and says "model" where
        OpenAI says "assistant"."""
        from app.services.negotiation_llm import _gemini_contents

        system, contents = _gemini_contents(
            [
                {"role": "system", "content": "You are Orion."},
                {"role": "user", "content": "Thanks for calling."},
                {"role": "assistant", "content": "Hi there."},
            ]
        )
        assert system == "You are Orion."
        assert [content.role for content in contents] == ["user", "model"]

    def test_gemini_native_turn_is_kept_for_replay(self):
        """Gemini rejects a replayed function call whose thought_signature is
        missing, and rebuilding the part from the portable form drops it - so
        the native turn rides along on the assistant message."""
        message = assistant_message(LLMReply(content="", native="<native Content>"))
        assert message["_gemini_content"] == "<native Content>"

    def test_native_turn_never_reaches_the_gateway(self):
        """Provider-native baggage must not go out on an LLM Gateway request."""
        history = [
            {"role": "user", "content": "Hello"},
            assistant_message(LLMReply(content="Hi", native="<native Content>")),
        ]
        assert all("_gemini_content" not in message for message in _portable(history))
        assert _portable(history)[1]["content"] == "Hi"

    def test_gemini_contents_replays_the_native_turn_verbatim(self):
        from app.services.negotiation_llm import _gemini_contents

        _, contents = _gemini_contents(
            [
                {"role": "user", "content": "Thanks for calling."},
                {"role": "assistant", "content": "", "_gemini_content": "<native Content>"},
            ]
        )
        assert contents[1] == "<native Content>"
