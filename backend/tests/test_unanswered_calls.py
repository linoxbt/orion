"""A call nobody answered must be reported as a call nobody answered.

Reported from a real attempt: the counterparty never picked up, and Orion
reported that the representative "didn't make a clear statement". There was no
representative. A call that rings out still leaves a second or two of
recording, and that was being transcribed and handed to a model which had been
told it was reading a negotiation - so it described one.
"""

import asyncio

import pytest

from app.models import NegotiationSession, NegotiationStatus
from app.services import verification


def _session(**kw) -> NegotiationSession:
    base = dict(
        task_id="11111111-1111-1111-1111-111111111111",
        provider="Comcast",
        phone_number="+15551234567",
    )
    base.update(kw)
    return NegotiationSession(**base)


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    saved = {}

    async def save(session):
        saved["session"] = session

    monkeypatch.setattr(verification, "save_session", save)
    return saved


class TestNeverAnswered:
    def test_an_unanswered_call_is_not_transcribed_at_all(self, monkeypatch):
        """Transcription is where the invention happened, so it must not run."""
        called = {"n": 0}

        def boom(*a, **kw):
            called["n"] += 1
            raise AssertionError("must not transcribe an unanswered call")

        monkeypatch.setattr(verification.httpx, "AsyncClient", boom)

        session = _session(status=NegotiationStatus.FAILED, answered_at=None)
        result = asyncio.run(verification.ingest_recording(session, "https://rec", 2))

        assert result is None
        assert called["n"] == 0

    def test_it_says_the_call_was_not_answered(self):
        session = _session(answered_at=None)
        asyncio.run(verification.ingest_recording(session, "https://rec", 2))
        assert session.outcome == "The call was not answered."
        assert session.verification_source == "not_answered"

    def test_a_factual_outcome_already_recorded_is_kept(self):
        """The status webhook writes the truth first; nothing may improve on it."""
        session = _session(answered_at=None, outcome="Nobody answered.")
        asyncio.run(verification.ingest_recording(session, "https://rec", 2))
        assert session.outcome == "Nobody answered."


class TestTooShortToBeAConversation:
    def test_a_two_second_call_is_not_read_as_a_negotiation(self, monkeypatch):
        def boom(*a, **kw):
            raise AssertionError("must not transcribe two seconds of audio")

        monkeypatch.setattr(verification.httpx, "AsyncClient", boom)

        session = _session(answered_at="2026-09-04T16:35:37+00:00")
        result = asyncio.run(verification.ingest_recording(session, "https://rec", 2))

        assert result is None
        assert session.verification_source == "too_short"
        assert "before anything was agreed" in session.outcome

    def test_the_floor_is_short_enough_to_allow_a_real_call(self):
        assert verification.MIN_CONVERSATION_SECONDS <= 15

    def test_an_unknown_duration_does_not_block_a_real_call(self, monkeypatch):
        """Twilio not sending a duration must not silently skip verification."""
        seen = {"ran": False}

        class Boom(Exception):
            pass

        def marker(*a, **kw):
            seen["ran"] = True
            raise Boom()

        monkeypatch.setattr(verification.httpx, "AsyncClient", marker)
        session = _session(answered_at="2026-09-04T16:35:37+00:00")

        with pytest.raises(Boom):
            asyncio.run(verification.ingest_recording(session, "https://rec", 0))
        assert seen["ran"] is True


class TestThePrompt:
    def test_it_does_not_presuppose_a_conversation(self):
        prompt = verification._EXTRACTION_PROMPT
        assert "may or may not have" in prompt
        assert "voicemail" in prompt.lower()

    def test_it_forbids_inventing_a_representative(self):
        assert "invents a person" in verification._EXTRACTION_PROMPT

    def test_a_fact_outranks_the_read_back(self):
        assert "not_answered" in verification._FACTUAL_OUTCOMES
        assert "too_short" in verification._FACTUAL_OUTCOMES
