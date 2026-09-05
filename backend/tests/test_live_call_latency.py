"""Nothing on the audio path may wait for a network call.

The relay's message pump reads the agent's messages and forwards its audio to
Twilio. Anything awaited inside a hook it calls stops that audio for exactly as
long as the await takes. Reading the room costs an HTTP round trip to the LLM
Gateway - useful, but never at the price of the call it is describing.
"""

import asyncio

from app.models import NegotiationSession
from app.services import tactics
from app.services.agent_bridge import NegotiationRelay


def a_session() -> NegotiationSession:
    return NegotiationSession(
        task_id="task-latency",
        user_id="owner",
        provider="Comcast",
        phone_number="+15551234567",
        vertical="cable_internet",
    )


class TestStanceIsOffThePump:
    def test_on_transcript_returns_before_the_classification_does(self, monkeypatch):
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_read(text: str):
            started.set()
            await release.wait()  # a gateway that never answers
            return {"stance": "softening", "has_authority": True, "advice": "Press now."}

        monkeypatch.setattr(tactics, "read_stance", slow_read)

        async def scenario() -> tuple[bool, bool]:
            relay = NegotiationRelay(None, a_session())
            # If this awaited the classification it would hang here forever.
            await asyncio.wait_for(relay.on_transcript("them", "We can look at that."), 1.0)
            await asyncio.wait_for(started.wait(), 1.0)
            in_flight = bool(relay._background)
            release.set()
            await asyncio.sleep(0)
            return True, in_flight

        returned, in_flight = asyncio.run(scenario())
        assert returned, "on_transcript blocked on the classification"
        assert in_flight, "the classification was never started"

    def test_a_failing_classification_does_not_escape(self, monkeypatch):
        """A raised exception inside the pump would tear down the call."""

        async def boom(text: str):
            raise RuntimeError("gateway down")

        monkeypatch.setattr(tactics, "read_stance", boom)

        async def scenario() -> None:
            relay = NegotiationRelay(None, a_session())
            await relay.on_transcript("them", "We can look at that.")
            for _ in range(50):
                await asyncio.sleep(0.01)
                if not relay._background:
                    return
            raise AssertionError("the classification never finished")

        asyncio.run(scenario())

    def test_the_agents_own_turns_are_not_classified(self, monkeypatch):
        calls: list[str] = []

        async def watched(text: str):
            calls.append(text)
            return None

        monkeypatch.setattr(tactics, "read_stance", watched)

        async def scenario() -> None:
            relay = NegotiationRelay(None, a_session())
            await relay.on_transcript("us", "Hello, this is Orion.")
            await asyncio.sleep(0.02)

        asyncio.run(scenario())
        assert calls == []
