"""Entry point for one live negotiation call: picks a voice backend and runs it.

Two implementations sit behind this, chosen by settings.voice_backend:

  agent_api  - app/services/agent_bridge.py: AssemblyAI's Voice Agent API holds
               the whole conversation over one websocket (STT + LLM + TTS +
               turn detection + tools), mu-law straight through from Twilio.
  stt_gemini - app/services/stt_bridge.py: AssemblyAI Universal-3.5 Pro
               streaming transcribes, AssemblyAI's LLM Gateway (Gemini) decides
               what to say, Google Cloud TTS speaks it, and this app owns the
               turn loop.

Both are wired to the same prompt, the same tools, and the same post-call
verification, so a run of calls can be compared backend to backend.

The Gemini Live bridge this replaced lives in git history (see the commit that
introduced AssemblyAI); nothing on the call path uses google-genai now, though
bill extraction still does.
"""

import logging

from fastapi import WebSocket

from app.config import settings
from app.models import NegotiationSession
from app.services import events
from app.services.agent_bridge import run_agent_bridge
from app.services.assemblyai import AssemblyAINotConfigured, require_api_key
from app.services.stt_bridge import run_stt_bridge
from app.services.verification import start_verification
from app.store import save_session

logger = logging.getLogger(__name__)

_BACKENDS = {
    "agent_api": run_agent_bridge,
    "stt_gemini": run_stt_bridge,
}


async def run_bridge(websocket: WebSocket, session: NegotiationSession) -> None:
    await websocket.accept()

    try:
        require_api_key()
    except AssemblyAINotConfigured:
        logger.error("AssemblyAI not configured - closing telephony bridge for task %s", session.task_id)
        await websocket.close(code=1011, reason="assemblyai_not_configured")
        return

    backend = _BACKENDS.get(settings.voice_backend)
    if backend is None:
        logger.error("Unknown VOICE_BACKEND %r for task %s", settings.voice_backend, session.task_id)
        await websocket.close(code=1011, reason="unknown_voice_backend")
        return

    session.voice_backend = settings.voice_backend
    await save_session(session)
    events.publish(session.task_id, {"type": "status", "status": "dialing", "backend": settings.voice_backend})

    try:
        await backend(websocket, session)
    finally:
        events.publish(session.task_id, {"type": "status", "status": "call_ended"})
        # The call is over; the recording is what proves what was agreed.
        await start_verification(session)
