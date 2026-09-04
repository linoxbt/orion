"""The agent must wait to be put through.

A real call to a retention desk is a queue: ringing, an IVR menu, then hold
music, for minutes. None of that is speech, so none of it produces a
transcript. Counting it as silence is how the agent hung up 53 seconds into a
call that was progressing perfectly normally - which makes reaching a
retention desk, the entire point of the product, impossible.
"""

import asyncio

import pytest

from app.services import voice_agent
from app.services.voice_agent import HOLD_PATIENCE_SECONDS, SILENCE_PROMPTS


class _Relay(voice_agent.VoiceAgentRelay):
    """The silence watcher on its own, with the socket work stubbed out."""

    def __init__(self):
        self.label = "test"
        self._heard_something = asyncio.Event()
        self._give_up = asyncio.Event()
        self._agent_quiet = asyncio.Event()
        self._agent_quiet.set()
        self.prompts: list[str] = []

    async def prompt_reply(self, instructions=None):
        self.prompts.append(instructions or "")


class TestWaitingToBePutThrough:
    def test_it_does_not_hang_up_while_on_hold(self):
        """The reported bug: 47 seconds of hold music ended the call."""
        async def scenario():
            relay = _Relay()
            watcher = asyncio.create_task(relay._watch_for_silence())
            # Far longer than the old 12+15+20 budget, and nobody has spoken.
            await asyncio.sleep(0.2)
            gave_up = relay._give_up.is_set()
            watcher.cancel()
            return gave_up, relay.prompts

        gave_up, prompts = asyncio.run(scenario())
        assert gave_up is False
        assert prompts == [], "must not talk into hold music"

    def test_it_waits_minutes_not_seconds(self):
        ladder = sum(delay for delay, _ in SILENCE_PROMPTS)
        assert HOLD_PATIENCE_SECONDS > ladder * 5
        assert HOLD_PATIENCE_SECONDS >= 300, "a retention queue runs for minutes"

    def test_it_does_eventually_give_up(self):
        """Bounded, because an open session bills by the second."""
        async def scenario():
            relay = _Relay()
            voice_agent.HOLD_PATIENCE_SECONDS = 0.05
            try:
                await relay._watch_for_silence()
            finally:
                voice_agent.HOLD_PATIENCE_SECONDS = HOLD_PATIENCE_SECONDS
            return relay._give_up.is_set()

        assert asyncio.run(scenario()) is True


class TestOnceSomebodySpeaks:
    def test_the_short_ladder_only_starts_after_speech(self):
        """A human who goes quiet mid-sentence is a different situation from
        a queue, and gets the shorter, more attentive treatment."""
        async def scenario():
            relay = _Relay()
            relay._heard_something.set()          # a person is on the line
            watcher = asyncio.create_task(relay._watch_for_silence())
            await asyncio.sleep(0.05)
            watcher.cancel()
            # It entered the ladder rather than the long hold wait.
            return relay._give_up.is_set()

        assert asyncio.run(scenario()) is False

    def test_hearing_someone_resets_the_ladder(self, monkeypatch):
        # The reply has to arrive comfortably inside the window, or this
        # tests the timeout rather than the reset.
        monkeypatch.setattr(voice_agent, "SILENCE_PROMPTS", ((0.10, "check in"),))

        async def scenario():
            relay = _Relay()
            relay._heard_something.set()
            watcher = asyncio.create_task(relay._watch_for_silence())
            for _ in range(4):
                await asyncio.sleep(0.02)
                relay._heard_something.set()   # they keep talking
            still_running = not relay._give_up.is_set()
            watcher.cancel()
            return still_running

        assert asyncio.run(scenario()) is True
