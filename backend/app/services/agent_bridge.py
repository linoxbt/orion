"""Orion's side of the call: the negotiation agent (VOICE_BACKEND=agent_api).

One websocket to AssemblyAI carries the whole agent - transcription, the LLM
holding the negotiation, TTS, turn detection and tool calling - so this module
is just the negotiation-specific configuration and the hooks that write what
happens onto the session. The relay itself is app/services/voice_agent.py.
"""

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


class NegotiationRelay(VoiceAgentRelay):
    def __init__(self, websocket: WebSocket, session: NegotiationSession) -> None:
        super().__init__(websocket, label=f"orion:{session.task_id}")
        self.session = session

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

    async def on_transcript(self, speaker: str, text: str) -> None:
        events.publish(
            self.session.task_id,
            {"type": "turn", "speaker": "rep" if speaker == "them" else "orion", "text": text},
        )

        # Only the far side's turns carry a position worth reading.
        if speaker != "them":
            return

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

    async def on_tool_call(self, name: str, arguments: dict[str, Any]) -> str:
        # press_keys needs to put audio on the call, not just record something.
        return await call_tools.dispatch(
            self.session, name, arguments, audio_sink=self.send_audio
        )


def session_update(session: NegotiationSession) -> dict[str, Any]:
    """The session.update payload for a negotiation call.

    Exposed so the config can be asserted on without opening a websocket -
    session_config() reads only the negotiation, so no live socket is needed.
    """
    return {"type": "session.update", "session": NegotiationRelay(None, session).session_config()}


async def run_agent_bridge(websocket: WebSocket, session: NegotiationSession) -> None:
    await NegotiationRelay(websocket, session).run()
