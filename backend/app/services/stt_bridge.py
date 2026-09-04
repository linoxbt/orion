"""Twilio <-> AssemblyAI streaming STT + an LLM + Google TTS (VOICE_BACKEND=stt_gemini).

The hand-rolled counterpart to agent_bridge.py. AssemblyAI's Universal-3.5 Pro
streaming model transcribes the call, a model chosen by settings.negotiation_llm
decides what to say (see app/services/negotiation_llm.py), and Google Cloud TTS
speaks it. This module owns the turn loop, barge-in and playback that the Voice
Agent API would otherwise own.

Two constraints shape the audio handling:

  - Twilio emits 20ms media frames, but the streaming API closes the socket
    with 3007 for anything outside 50-1000ms. Frames are coalesced to 100ms
    before being forwarded.
  - Phone audio stays at its native 8kHz mu-law end to end. Upsampling to 16kHz
    measurably hurts accuracy, and TTS is requested as mu-law directly, so no
    resampling happens anywhere on this path.
"""

import asyncio
import base64
import json
import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from app.models import NegotiationSession
from app.services import call_tools, events, negotiation_llm, prompting, tts
from app.services.assemblyai import STREAMING_WS, rest_headers
from app.store import save_session

logger = logging.getLogger(__name__)

SAMPLE_RATE = 8000
# 8kHz mu-law is 1 byte per sample, so 100ms is 800 bytes - comfortably inside
# the streaming API's 50-1000ms window with room for jitter.
CHUNK_MS = 100
CHUNK_BYTES = SAMPLE_RATE * CHUNK_MS // 1000
# One Twilio media frame is 20ms of audio.
TWILIO_FRAME_BYTES = SAMPLE_RATE * 20 // 1000
MAX_TOOL_ROUNDS = 3

# How long a closing line may run before the call is cut regardless, and the
# margin afterwards covering audio still buffered at Twilio.
GOODBYE_PATIENCE = 20.0
GOODBYE_TAIL = 1.5


def _streaming_url(session: NegotiationSession) -> str:
    params = {
        # Singular string here. The plural speech_models array is pre-recorded
        # only - mixing the two up is the most common streaming mistake.
        "speech_model": "universal-3-5-pro",
        "encoding": "pcm_mulaw",
        "sample_rate": SAMPLE_RATE,
        # mode is the primary latency/accuracy control; it sets the
        # turn-detection defaults so the individual silence knobs stay unset.
        "mode": "balanced",
        "keyterms_prompt": json.dumps(prompting.keyterms(session)),
    }
    # Omitted for English so the model code-switches freely; set otherwise, to
    # steer per-token toward the language the call is actually in.
    if session.language != "en":
        params["language_code"] = session.language
    return f"{STREAMING_WS}?{urlencode(params)}"


async def run_stt_bridge(websocket: WebSocket, session: NegotiationSession) -> None:
    stream_sid: str | None = None
    inbound_buffer = bytearray()
    playback: asyncio.Task | None = None
    hang_up = asyncio.Event()
    history: list[dict[str, Any]] = [
        {"role": "system", "content": prompting.system_instruction(session)}
    ]

    async with ws_connect(_streaming_url(session), additional_headers=rest_headers()) as stt:

        async def send_to_twilio(mulaw: bytes) -> None:
            if stream_sid is None:
                return
            for offset in range(0, len(mulaw), TWILIO_FRAME_BYTES):
                frame = mulaw[offset : offset + TWILIO_FRAME_BYTES]
                await websocket.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": base64.b64encode(frame).decode("ascii")},
                        }
                    )
                )

        async def clear_twilio_buffer() -> None:
            if stream_sid is None:
                return
            await websocket.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))

        async def speak(text: str) -> None:
            """Synthesise and play one agent turn, then bias the next user turn with it."""
            if not text.strip():
                return
            events.publish(session.task_id, {"type": "turn", "speaker": "orion", "text": text})
            await send_to_twilio(await tts.synthesize_mulaw(text))
            # agent_context tells the model what the agent just said, which
            # sharpens the next turn - especially short replies, spelled names
            # and confirmation numbers read back.
            await stt.send(
                json.dumps({"type": "UpdateConfiguration", "agent_context": text[:1500]})
            )

        async def end_call() -> None:
            """The agent asked to hang up. Flag it; the closing line is still
            being spoken, and wait_for_hangup is what waits for it."""
            hang_up.set()

        async def respond(rep_said: str) -> None:
            history.append({"role": "user", "content": rep_said})
            reply = await negotiation_llm.complete(history, call_tools.TOOL_DEFINITIONS)

            rounds = 0
            while reply.tool_calls and rounds < MAX_TOOL_ROUNDS:
                history.append(negotiation_llm.assistant_message(reply))
                for call in reply.tool_calls:
                    result = await call_tools.dispatch(
                        session,
                        call.name,
                        call.arguments,
                        audio_sink=send_to_twilio,
                        on_end_call=end_call,
                    )
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": result,
                        }
                    )
                reply = await negotiation_llm.complete(history, call_tools.TOOL_DEFINITIONS)
                rounds += 1

            history.append({"role": "assistant", "content": reply.content})
            await speak(reply.content)

        async def pump_twilio_to_stt() -> None:
            nonlocal stream_sid
            try:
                while True:
                    event = json.loads(await websocket.receive_text())
                    kind = event.get("event")
                    if kind == "start":
                        stream_sid = event["start"]["streamSid"]
                        session.call_sid = event["start"].get("callSid", session.call_sid)
                        await save_session(session)
                        events.publish(session.task_id, {"type": "status", "status": "connected"})
                        await speak(prompting.greeting(session))
                    elif kind == "media":
                        inbound_buffer.extend(base64.b64decode(event["media"]["payload"]))
                        while len(inbound_buffer) >= CHUNK_BYTES:
                            await stt.send(bytes(inbound_buffer[:CHUNK_BYTES]))
                            del inbound_buffer[:CHUNK_BYTES]
                    elif kind == "stop":
                        break
            except WebSocketDisconnect:
                logger.info("Twilio websocket disconnected for task %s", session.task_id)
            except ConnectionClosed:
                logger.info("Streaming websocket closed for task %s", session.task_id)
            finally:
                # An abandoned streaming session keeps billing until the 3-hour
                # cap, so this is not optional.
                try:
                    await stt.send(json.dumps({"type": "Terminate"}))
                except ConnectionClosed:
                    pass

        async def pump_stt_to_agent() -> None:
            nonlocal playback
            async for raw in stt:
                message = json.loads(raw)
                kind = message.get("type")

                if kind == "SpeechStarted":
                    # Barge-in: the rep talked over us, so drop whatever Twilio
                    # still has queued and abandon the in-flight reply.
                    if playback is not None and not playback.done():
                        playback.cancel()
                        await clear_twilio_buffer()

                elif kind == "Turn" and message.get("end_of_turn"):
                    transcript = (message.get("transcript") or "").strip()
                    if not transcript:
                        continue
                    events.publish(
                        session.task_id, {"type": "turn", "speaker": "rep", "text": transcript}
                    )
                    playback = asyncio.create_task(respond(transcript))

                elif kind == "Termination":
                    break

        async def wait_for_hangup() -> None:
            await hang_up.wait()
            # end_call fires from inside the turn that is still being spoken,
            # and <Connect> is terminal: Twilio ends the call the instant this
            # socket closes. So let the goodbye finish playing first.
            if playback is not None and not playback.done():
                try:
                    await asyncio.wait_for(asyncio.shield(playback), timeout=GOODBYE_PATIENCE)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            # Audio sits queued at Twilio ahead of being heard, so silence on
            # this side is slightly early.
            await asyncio.sleep(GOODBYE_TAIL)
            logger.info("Agent ended the call for %s", session.task_id)

        pumps = asyncio.gather(pump_twilio_to_stt(), pump_stt_to_agent())
        ended = asyncio.create_task(wait_for_hangup())
        try:
            await asyncio.wait({pumps, ended}, return_when=asyncio.FIRST_COMPLETED)
            if pumps.done():
                pumps.result()
        except (WebSocketDisconnect, ConnectionClosed):
            pass
        finally:
            ended.cancel()
            pumps.cancel()
            if playback is not None and not playback.done():
                playback.cancel()
