"""Run the negotiation agent from a browser instead of over a phone line.

Twilio's trial tier blocks the `<Stream>` verb outright, so there is no phone
path on a free account. The Voice Agent API is designed to deploy to a browser
as readily as to a phone, so this exposes exactly the same agent - same system
prompt, same greeting, same tools, same playbooks - over the browser's
microphone.

Two endpoints, because the browser must never hold the API key:

  POST /api/browser/{task_id}/session  mints a short-lived single-use token and
                                       returns the session config to open with
  POST /api/browser/{task_id}/tool     runs a tool the agent called, server-side

The tool endpoint is what keeps this honest. The browser relays `tool.call`
events here rather than answering them itself, so `log_offer`,
`record_confirmation_number` and `provide_verification` write to the same
session, publish to the same event feed, and read from the same encrypted
vault as they do on a phone call. Verification values in particular never
reach the browser's own code - only the agent's audio stream.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.models import NegotiationSession
from app.security import require_owned_session
from app.services import call_tools, events, prompting, tactics
from app.services.languages import voice_for
from app.services.ratelimit import limit
from app.services.assemblyai import AssemblyAINotConfigured, mint_agent_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browser", tags=["browser-agent"])

# The browser speaks the Voice Agent API's default format rather than Twilio's
# mu-law: 24kHz PCM16, base64 inside JSON events.
BROWSER_AUDIO = {"encoding": "audio/pcm"}


class BrowserSession(BaseModel):
    token: str
    session: dict[str, Any]


@router.post("/{task_id}/session", response_model=BrowserSession)
async def create_browser_session(
    task_id: str, session: NegotiationSession = Depends(require_owned_session)
) -> BrowserSession:
    """Mint a token and hand back the agent configuration to open with."""
    # Each session opened here is billable for as long as it stays open.
    limit(f"agent-session:{session.user_id or task_id}", max_calls=10, per_seconds=300)

    try:
        token = await mint_agent_token()
    except AssemblyAINotConfigured as exc:
        raise HTTPException(status_code=503, detail="assemblyai_not_configured") from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Could not mint an agent token: %s", exc)
        raise HTTPException(status_code=502, detail="token_mint_failed") from exc

    events.publish(task_id, {"type": "status", "status": "connected", "backend": "browser"})

    return BrowserSession(
        token=token,
        session={
            "system_prompt": prompting.system_instruction(session),
            "greeting": prompting.greeting(session),
            "input": {
                "format": BROWSER_AUDIO,
                "keyterms": prompting.keyterms(session),
                "turn_detection": {"interrupt_response": True},
            },
            "output": {
                "voice": voice_for(session.language, settings.assemblyai_voice),
                "format": BROWSER_AUDIO,
            },
            "tools": call_tools.TOOL_DEFINITIONS,
        },
    )


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class ToolCallResult(BaseModel):
    result: str


@router.post("/{task_id}/tool", response_model=ToolCallResult)
async def run_tool(
    body: ToolCallRequest, session: NegotiationSession = Depends(require_owned_session)
) -> ToolCallResult:
    """Execute one tool the agent called, against the real session.

    press_keys is accepted but does nothing here: there is no phone line to put
    DTMF on, and saying so plainly is better than letting the agent believe it
    navigated a menu that was never there.
    """

    if body.name == "press_keys":
        return ToolCallResult(result="There is no phone keypad on this call.")

    result = await call_tools.dispatch(session, body.name, body.arguments)
    return ToolCallResult(result=result)


class TranscriptRequest(BaseModel):
    speaker: str
    text: str


@router.post("/{task_id}/transcript")
async def record_transcript(
    task_id: str,
    body: TranscriptRequest,
    _session: NegotiationSession = Depends(require_owned_session),
) -> dict[str, object]:
    """Relay a finished turn onto the live event feed, so the dashboard shows a
    browser call exactly as it shows a phone call."""

    text = body.text.strip()
    if not text:
        return {"status": "ok"}

    is_agent = body.speaker == "orion"
    events.publish(
        task_id, {"type": "turn", "speaker": "orion" if is_agent else "rep", "text": text}
    )

    # Read the other side's position, same as the phone path. The rehearsal is
    # only useful if it behaves like the real call.
    if not is_agent:
        reading = await tactics.read_stance(text)
        if reading is not None:
            events.publish(task_id, {"type": "stance", **reading})
            return {"status": "ok", "coaching": tactics.coaching_note(reading)}

    return {"status": "ok"}
