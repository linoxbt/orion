"""The agent has to hang up when the conversation is over.

Nobody else can. The customer is not on the call, the provider's rep says
goodbye and waits, and the media stream stays open - billing on both Twilio and
AssemblyAI - until this side closes it. <Connect><Stream> is terminal, so
closing the stream is what ends the call.

The other half of this is timing: end_call fires from inside the turn that is
still being spoken, so hanging up the instant the tool returns cuts the goodbye
off mid-word.
"""

import asyncio

import pytest

from app.models import NegotiationSession
from app.store import init_db
from app.services import agent_bridge, call_tools
from app.services.agent_bridge import NegotiationRelay


async def _wait_for(event: asyncio.Event, timeout: float = 2.0) -> None:
    """Give the background hang-up task a chance to run, without sleeping for
    a fixed slice of wall clock in a test suite."""
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass


def a_session() -> NegotiationSession:
    return NegotiationSession(
        task_id="task-hangup",
        user_id="owner",
        provider="Comcast",
        phone_number="+15551234567",
        vertical="cable_internet",
    )


@pytest.fixture
def store(isolated_db):
    """A schema-backed database of this test's own.

    end_call persists the session as it records the outcome. Without this the
    write lands in whatever orion.db happens to be sitting in the working
    directory - which passes on a developer machine that has one and fails on a
    fresh checkout, which is exactly how these four tests went red in CI while
    staying green here.
    """
    asyncio.run(init_db())


class TestEndCallTool:
    def test_it_is_offered_to_the_agent(self):
        names = {tool["name"] for tool in call_tools.TOOL_DEFINITIONS}
        assert "end_call" in names

    def test_it_hangs_up(self, store):
        session = a_session()
        hung_up = asyncio.Event()

        async def on_end_call() -> None:
            hung_up.set()

        result = asyncio.run(
            call_tools.dispatch(
                session, "end_call", {"reason": "Agreed 20 dollars off."}, on_end_call=on_end_call
            )
        )
        assert hung_up.is_set()
        assert "ending" in result.lower()

    def test_the_reason_becomes_the_outcome(self, store):
        session = a_session()
        asyncio.run(call_tools.dispatch(session, "end_call", {"reason": "They refused."}))
        assert session.outcome == "They refused."

    def test_it_does_not_overwrite_an_outcome_already_recorded(self, store):
        """log_offer and record_confirmation_number know more than a one-line
        reason does. The tool that ran first was closer to the facts."""
        session = a_session()
        session.outcome = "Agreed 69.99 for 12 months, confirmation A1B2C3."
        asyncio.run(call_tools.dispatch(session, "end_call", {"reason": "Done."}))
        assert session.outcome == "Agreed 69.99 for 12 months, confirmation A1B2C3."

    def test_it_survives_a_rehearsal_with_nothing_to_hang_up(self, store):
        """The browser rehearsal has no phone call. The tool still records the
        outcome rather than erroring at the agent mid-sentence."""
        session = a_session()
        result = asyncio.run(call_tools.dispatch(session, "end_call", {"reason": "All done."}))
        assert "ending" in result.lower()
        assert session.outcome == "All done."


class TestGoodbyeIsNotCutOff:
    def test_it_waits_for_the_agent_to_stop_speaking(self, monkeypatch):
        monkeypatch.setattr(agent_bridge, "GOODBYE_TAIL", 0.01)
        monkeypatch.setattr(agent_bridge, "GOODBYE_PATIENCE", 5.0)

        async def scenario() -> tuple[bool, bool]:
            relay = NegotiationRelay(None, a_session())
            relay._agent_quiet.clear()  # mid-goodbye

            await relay.finish()
            await asyncio.sleep(0.05)
            cut_off = relay._give_up.is_set()

            relay._agent_quiet.set()
            await _wait_for(relay._give_up)
            return cut_off, relay._give_up.is_set()

        cut_off, hung_up = asyncio.run(scenario())
        assert not cut_off, "hung up while still speaking"
        assert hung_up, "never hung up after the goodbye finished"

    def test_a_goodbye_that_never_ends_still_hangs_up(self, monkeypatch):
        """A stuck TTS stream must not hold a billable call open forever."""
        monkeypatch.setattr(agent_bridge, "GOODBYE_PATIENCE", 0.05)
        monkeypatch.setattr(agent_bridge, "GOODBYE_TAIL", 0.01)

        async def scenario() -> bool:
            relay = NegotiationRelay(None, a_session())
            relay._agent_quiet.clear()
            await relay.finish()
            await _wait_for(relay._give_up)
            return relay._give_up.is_set()

        assert asyncio.run(scenario())
