"""Two writers, one negotiation, nothing lost.

During a live call three things write to the same row: the agent's tools,
Twilio's status webhook, and the recording pass. A negotiation is stored as one
JSON document, so every save writes all of it - and each writer used to hold a
copy loaded at a different moment, which meant the last save silently erased
whatever the others had recorded.

The case that matters: the agent records a confirmation number, and a webhook
that loaded the session a second earlier writes "the call ended" on top of it.
The number is the only thing a saving can be proven with.
"""

import asyncio

import pytest

from app.models import NegotiationSession, NegotiationStatus
from app.services import call_tools
from app.store import get_session, init_db, mutate, save_session


def _session() -> NegotiationSession:
    return NegotiationSession(
        task_id="33333333-3333-3333-3333-333333333333",
        user_id="owner",
        provider="Comcast",
        phone_number="+15551234567",
    )


@pytest.fixture
def store(isolated_db):
    asyncio.run(init_db())


class TestNothingIsClobbered:
    def test_a_stale_writer_cannot_erase_a_confirmation_number(self, store):
        async def scenario() -> NegotiationSession:
            session = _session()
            await save_session(session)

            # A webhook loads the session here, before the tool call.
            stale = await get_session(session.task_id)

            await call_tools.dispatch(
                session,
                "record_confirmation_number",
                {"confirmation_number": "A1B2C3", "new_monthly_rate": 69.99},
            )

            # ...and only writes afterwards, through the same locked path.
            def ended(current: NegotiationSession) -> None:
                current.status = NegotiationStatus.COMPLETED

            assert stale.confirmation_number is None  # the stale copy never saw it
            await mutate(session.task_id, ended)
            return await get_session(session.task_id)

        final = asyncio.run(scenario())
        assert final.confirmation_number == "A1B2C3", "the confirmation number was erased"
        assert final.new_rate == 69.99
        assert final.status is NegotiationStatus.COMPLETED

    def test_concurrent_mutations_all_survive(self, store):
        """Ten writers at once, each recording one offer."""

        async def scenario() -> NegotiationSession:
            session = _session()
            await save_session(session)

            async def add(i: int) -> None:
                await mutate(
                    session.task_id,
                    lambda s, i=i: s.offers.append(
                        __import__("app.models", fromlist=["Offer"]).Offer(description=f"offer {i}")
                    ),
                )

            await asyncio.gather(*(add(i) for i in range(10)))
            return await get_session(session.task_id)

        final = asyncio.run(scenario())
        assert len(final.offers) == 10, f"lost {10 - len(final.offers)} concurrent writes"

    def test_the_live_session_and_the_row_agree(self, store):
        """The relay keeps its copy for the length of the call, so a tool has to
        update both or the agent argues from a state the database disagrees with."""

        async def scenario():
            session = _session()
            await save_session(session)
            await call_tools.dispatch(session, "end_call", {"reason": "All done."})
            return session, await get_session(session.task_id)

        live, stored = asyncio.run(scenario())
        assert live.outcome == "All done."
        assert stored.outcome == "All done."

    def test_mutating_a_negotiation_that_is_gone_is_not_an_error(self, store):
        assert asyncio.run(mutate("44444444-4444-4444-4444-444444444444", lambda s: None)) is None
