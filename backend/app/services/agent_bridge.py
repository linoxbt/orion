"""Orion's side of the call: the negotiation agent (VOICE_BACKEND=agent_api).

One websocket to AssemblyAI carries the whole agent - transcription, the LLM
holding the negotiation, TTS, turn detection and tool calling - so this module
is just the negotiation-specific configuration and the hooks that write what
happens onto the session. The relay itself is app/services/voice_agent.py.
"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from app.config import settings
from app.models import NegotiationSession
from app.services import call_tools, events, prompting, tactics
from app.services.languages import voice_for
from app.services.voice_agent import PCMU, VoiceAgentRelay
from app.store import save_session

logger = logging.getLogger(__name__)

# How long to let a closing line run before hanging up regardless, and the
# margin afterwards that covers audio still buffered at Twilio.
GOODBYE_PATIENCE = 20.0
GOODBYE_TAIL = 1.5


class NegotiationRelay(VoiceAgentRelay):
    def __init__(self, websocket: WebSocket, session: NegotiationSession) -> None:
        super().__init__(websocket, label=f"orion:{session.task_id}")
        self.session = session
        # Work started by this relay that outlives the call it was started
        # from: stance classifications (see on_transcript) and the delayed
        # hang-up. Held in a set because asyncio keeps only a weak reference to
        # a running task and will collect one nobody is watching.
        self._background: set[asyncio.Task] = set()

    def session_config(self) -> dict[str, Any]:
        return {
            "system_prompt": prompting.system_instruction(self.session),
            "greeting": prompting.greeting(self.session),
            "input": {
                "format": PCMU,
                "keyterms": prompting.keyterms(self.session),
                "turn_detection": {"interrupt_response": True},
            },
            "output": {
                "voice": voice_for(self.session.language, settings.assemblyai_voice),
                "format": PCMU,
            },
            "tools": call_tools.TOOL_DEFINITIONS,
        }

    async def on_start(self, start_event: dict[str, Any]) -> None:
        self.session.call_sid = start_event.get("callSid", self.session.call_sid)
        await save_session(self.session)

    async def on_ready(self) -> None:
        events.publish(self.session.task_id, {"type": "status", "status": "connected"})

    async def on_speaking(self, speaking: bool) -> None:
        # Who currently holds the floor, so the call screen can show Orion
        # rather than the company while Orion is the one talking.
        events.publish(
            self.session.task_id,
            {"type": "speaking", "who": "orion" if speaking else "rep"},
        )

    async def on_transcript(self, speaker: str, text: str) -> None:
        events.publish(
            self.session.task_id,
            {"type": "turn", "speaker": "rep" if speaker == "them" else "orion", "text": text},
        )

        # Only the far side's turns carry a position worth reading.
        if speaker != "them":
            return

        # Off the pump, deliberately.
        #
        # This hook is awaited by the loop that reads the agent's messages and
        # forwards its audio to Twilio. Reading the room costs an HTTP round
        # trip to the LLM Gateway, and awaiting it here meant no audio moved
        # for its duration - a few hundred milliseconds of dead air mid-call on
        # a good day, and up to the gateway's whole timeout on a bad one. The
        # classification is useful, but never at the price of the call it is
        # describing.
        self._spawn(self._read_the_room(text))

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _read_the_room(self, text: str) -> None:
        """Classify one representative turn and feed it back into the agent."""
        try:
            reading = await tactics.read_stance(text)
            if reading is None:
                return

            events.publish(self.session.task_id, {"type": "stance", **reading})
            # agent_context biases the next turn - this is where the read of the
            # room actually changes what the agent says next, rather than just
            # decorating a dashboard.
            await self.send_configuration_update(
                {"session": {"input": {"agent_context": tactics.coaching_note(reading)}}}
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a stalled read must not end a call
            logger.warning("[orion:%s] Could not read the room: %s", self.session.task_id, exc)

    async def on_tool_call(self, name: str, arguments: dict[str, Any]) -> str:
        # press_keys needs to put audio on the call, not just record something,
        # and end_call needs to actually hang it up rather than leaving the
        # agent sitting silently on an open, billing line.
        return await call_tools.dispatch(
            self.session,
            name,
            arguments,
            audio_sink=self.send_audio,
            on_end_call=self.finish,
        )

    async def finish(self) -> None:
        """Hang up once the agent has finished saying goodbye.

        Returning from the tool call is not the end of the turn: the closing
        line is still being spoken. Tearing the stream down here would cut it
        off mid-syllable, and the goodbye is the part of the call the other
        person remembers. So this hands off to a background task and lets the
        tool result go back immediately - blocking inside the handler would
        stall every other message on the socket for the same three seconds.
        """
        self._spawn(self._hang_up_after_goodbye())

    async def _hang_up_after_goodbye(self) -> None:
        # A beat before listening for quiet: between turns the agent is already
        # quiet, and the tool result ("say nothing further") may still prompt
        # one last line. Checking immediately would cut that line off.
        await asyncio.sleep(GOODBYE_TAIL)
        try:
            await asyncio.wait_for(self._agent_quiet.wait(), timeout=GOODBYE_PATIENCE)
        except asyncio.TimeoutError:
            logger.info("[%s] Goodbye ran long; hanging up anyway", self.label)
        else:
            # The audio is queued at Twilio ahead of being played, so quiet on
            # this side is slightly early. A beat of margin costs nothing.
            await asyncio.sleep(GOODBYE_TAIL)
        logger.info("[%s] Agent ended the call", self.label)
        self._give_up.set()


def session_update(session: NegotiationSession) -> dict[str, Any]:
    """The session.update payload for a negotiation call.

    Exposed so the config can be asserted on without opening a websocket -
    session_config() reads only the negotiation, so no live socket is needed.
    """
    return {"type": "session.update", "session": NegotiationRelay(None, session).session_config()}


async def run_agent_bridge(websocket: WebSocket, session: NegotiationSession) -> None:
    await NegotiationRelay(websocket, session).run()
