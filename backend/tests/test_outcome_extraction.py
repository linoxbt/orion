"""Which model decides whether somebody gets billed.

The outcome extraction reads a saving, a rate and a confirmation number out of
a call transcript. It was running on a 4B model - not by choice, but because
that is the only model this AssemblyAI account can reach on the LLM Gateway.
The Gemini key configured for bill extraction reaches a far stronger one, so
this job goes there first and falls back rather than depending on it.
"""

import asyncio

import pytest

from app.config import settings
from app.services import gemini, verification


class TestExtractionPrefersTheStrongerModel:
    def test_gemini_is_used_when_it_is_configured(self, monkeypatch):
        seen = {}

        async def fake(instruction, content):
            seen["instruction"] = instruction
            seen["content"] = content
            return {"agreed": True, "outcome": "Agreed."}

        monkeypatch.setattr(settings, "gemini_api_key", "test-key")
        monkeypatch.setattr(gemini, "structured_json", fake)

        async def never(*a, **kw):
            raise AssertionError("the gateway should not have been asked")

        monkeypatch.setattr(verification, "llm_gateway_json", never)

        result = asyncio.run(verification._extract("Speaker A: hello"))

        assert result == {"agreed": True, "outcome": "Agreed."}
        assert "invents a person" in seen["instruction"]  # the real prompt
        assert seen["content"] == "Speaker A: hello"

    def test_the_gateway_covers_a_deployment_with_no_gemini_key(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")

        async def gateway(messages, **kw):
            return {"agreed": False, "outcome": "Refused."}

        monkeypatch.setattr(verification, "llm_gateway_json", gateway)

        assert asyncio.run(verification._extract("x"))["outcome"] == "Refused."

    def test_a_gemini_failure_falls_back_rather_than_losing_the_outcome(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "test-key")

        async def broken(instruction, content):
            return None

        async def gateway(messages, **kw):
            return {"agreed": True, "outcome": "From the gateway."}

        monkeypatch.setattr(gemini, "structured_json", broken)
        monkeypatch.setattr(verification, "llm_gateway_json", gateway)

        assert asyncio.run(verification._extract("x"))["outcome"] == "From the gateway."

    def test_both_failing_returns_nothing_rather_than_a_guess(self, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "test-key")

        async def broken(*a, **kw):
            return None

        monkeypatch.setattr(gemini, "structured_json", broken)
        monkeypatch.setattr(verification, "llm_gateway_json", broken)

        assert asyncio.run(verification._extract("x")) is None
