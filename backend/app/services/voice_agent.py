"""Relay between one Twilio Media Stream and one AssemblyAI Voice Agent API session.

Orion's negotiation agent (app/services/agent_bridge.py) runs on this.
Subclasses supply the session config and react to transcripts and tool calls;
everything below - the audio passthrough, the ready gate, barge-in, the keypad
path, and the tool-result timing - lives here rather than in the subclass.

Two details this class exists to get right:

  - Audio is never transcoded. Twilio Media Streams carry base64 G.711 mu-law
    at 8kHz, and setting BOTH input and output encoding to "audio/pcmu" makes
    the Voice Agent API speak exactly that. Setting only the input is the
    classic mistake: the agent replies in 24kHz PCM that Twilio can't play.
  - The audio field name is asymmetric. Going TO the agent it is "audio"
    (input.audio); coming BACK it is "data" (reply.audio).
"""

import asyncio
import base64
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from app.services.assemblyai import AGENTS_WS, agent_headers

logger = logging.getLogger(__name__)

# Twilio's native wire format, byte-compatible with the Voice Agent API's.
PCMU = {"encoding": "audio/pcmu"}

# How long to wait before concluding that nobody is ever going to speak.
#
# Reaching a retention desk means a queue: ringing, an IVR menu, then hold
# music, for minutes. None of that is speech, so none of it produces a
# transcript, and treating it as silence is how the agent came to hang up 53
# seconds into a real call that was progressing perfectly normally. A person
# waiting to be put through does not give up after a minute, and neither
# should this.
HOLD_PATIENCE_SECONDS = 420.0

# What a person does when the line goes quiet: check, try once more, then go.
# Seconds to wait, and what to say when the wait runs out.
#
# These apply only AFTER somebody has actually spoken. Before that, the
# silence is a queue rather than an unresponsive human, and asking hold music
# whether it is still there is pointless.
SILENCE_PROMPTS: tuple[tuple[float, str], ...] = (
    (
        12.0,
        "You have had no response for several seconds. Politely check whether the person "
        "is still there - for example 'Hello, are you still there?' - and keep it to one "
        "short line.",
    ),
    (
        15.0,
        "Still no response. Say once more that you can't hear anything and ask them to "
        "speak up if they are there. One short line.",
    ),
    (
        20.0,
        "There has been no response at all. Say politely that you'll try again another "
        "time, thank them, and say goodbye. One short line.",
    ),
)

# One Twilio media frame is 20ms of 8kHz mu-law.
TWILIO_FRAME_BYTES = 160


class VoiceAgentRelay:
    """One call, relayed. Subclass and override the hooks you care about."""

    def __init__(self, websocket: WebSocket, label: str = "agent") -> None:
        self.websocket = websocket
        self.label = label
        self.stream_sid: str | None = None
        self.ready = asyncio.Event()
        # Tool results wait for reply.done: a barge-in discards them rather
        # than answering something the human already talked over.
        self._pending_tool_results: list[dict[str, Any]] = []
        self._agent = None
        # Set whenever the far end says something, so the silence ladder can
        # start over rather than marching toward hanging up on a live call.
        self._heard_something = asyncio.Event()
        self._give_up = asyncio.Event()
        # Set while the agent has the floor. Counting silence against the other
        # side while this agent is still talking is what made it interrupt its
        # own greeting and then escalate to hanging up.
        self._agent_speaking = asyncio.Event()
        # Set whenever the agent stops speaking, so the silence watcher can
        # wait on it rather than polling.
        self._agent_quiet = asyncio.Event()
        self._agent_quiet.set()

    # ---- to be supplied by subclasses -------------------------------------

    def session_config(self) -> dict[str, Any]:
        raise NotImplementedError

    async def on_ready(self) -> None:
        """Called once the agent session is live and audio may start flowing."""

    async def on_start(self, start_event: dict[str, Any]) -> None:
        """Called with Twilio's "start" event payload."""

    async def on_transcript(self, speaker: str, text: str) -> None:
        """speaker is "them" (the far end) or "us" (this agent)."""

    async def on_tool_call(self, name: str, arguments: dict[str, Any]) -> str:
        return f"Unknown tool: {name}"

    async def on_interrupted(self) -> None:
        """Called when the far end talked over this agent."""

    async def on_speaking(self, speaking: bool) -> None:
        """Called when this agent starts or stops holding the floor.

        Reported as it happens rather than inferred from transcripts, which
        arrive after the words are spoken - a UI driven by transcripts is
        always a beat behind the call it is describing.
        """

    # ---- relay ------------------------------------------------------------

    async def send_configuration_update(self, update: dict[str, Any]) -> None:
        if self._agent is not None:
            await self._agent.send(json.dumps({"type": "session.update", **update}))

    async def prompt_reply(self, instructions: str | None = None) -> None:
        """Make the agent speak without waiting for the other side.

        The API waits for a user utterance, so if nobody ever answers, no turn
        ever ends and the agent sits silent indefinitely - which is not what a
        person does when a line goes quiet. reply.create is the documented way
        to break that.
        """
        if self._agent is None:
            return
        payload: dict[str, Any] = {"type": "reply.create"}
        if instructions:
            payload["instructions"] = instructions
        await self._agent.send(json.dumps(payload))

    async def _watch_for_silence(self) -> None:
        """Wait to reach a person, then watch for that person going quiet.

        Two regimes, because the same silence means two different things.

        Before anyone has spoken, this call is in a queue - ringing, an IVR,
        hold music - and the only sane response is to wait. Prompting into hold
        music accomplishes nothing, and hanging up guarantees never reaching
        the retention desk that is the entire point of the call.

        Once somebody has spoken, silence means a person stopped talking, and
        the ladder below is what a person would do about it.

        Idle time on an open session is billable, so the wait is bounded rather
        than indefinite.
        """
        if not self._heard_something.is_set():
            logger.info("[%s] On the line, waiting to reach a person", self.label)
            try:
                await asyncio.wait_for(
                    self._heard_something.wait(), timeout=HOLD_PATIENCE_SECONDS
                )
            except asyncio.TimeoutError:
                logger.info(
                    "[%s] Nobody spoke in %.0f seconds; ending the call",
                    self.label,
                    HOLD_PATIENCE_SECONDS,
                )
                self._give_up.set()
                return
            self._heard_something.clear()

        stage = 0
        while stage < len(SILENCE_PROMPTS):
            delay, instructions = SILENCE_PROMPTS[stage]
            # Never count while the agent is mid-sentence - and wait on an
            # event rather than polling for it.
            await self._agent_quiet.wait()
            try:
                await asyncio.wait_for(self._heard_something.wait(), timeout=delay)
            except asyncio.TimeoutError:
                logger.info(
                    "[%s] %.0fs without a reply; checking in (%d of %d)",
                    self.label,
                    delay,
                    stage + 1,
                    len(SILENCE_PROMPTS),
                )
                await self.prompt_reply(instructions)
                stage += 1
                continue
            # Someone spoke: the call is alive, so start the ladder again from
            # the top. A loop rather than recursion - a long call turns every
            # utterance into a stack frame otherwise.
            self._heard_something.clear()
            stage = 0

        logger.info("[%s] No response after three prompts; ending the call", self.label)
        self._give_up.set()

    async def _send_media(self, payload_b64: str) -> None:
        if self.stream_sid is None:
            return
        await self.websocket.send_text(
            json.dumps(
                {"event": "media", "streamSid": self.stream_sid, "media": {"payload": payload_b64}}
            )
        )

    async def send_audio(self, mulaw: bytes) -> None:
        """Push raw 8kHz mu-law into the call, in Twilio-sized frames.

        This is how DTMF reaches an IVR: the tones are synthesised as ordinary
        audio (app/services/dtmf.py) and sent down the same stream as speech,
        rather than redirecting the call to a <Play digits=""> verb, which
        would tear the media stream down mid-call.
        """
        for offset in range(0, len(mulaw), TWILIO_FRAME_BYTES):
            frame = mulaw[offset : offset + TWILIO_FRAME_BYTES]
            await self._send_media(base64.b64encode(frame).decode("ascii"))

    async def _clear_twilio_buffer(self) -> None:
        if self.stream_sid is None:
            return
        await self.websocket.send_text(
            json.dumps({"event": "clear", "streamSid": self.stream_sid})
        )

    async def run(self) -> None:
        async with ws_connect(AGENTS_WS, additional_headers=agent_headers()) as agent:
            self._agent = agent
            # Sent immediately - the API expects configuration up front, and
            # waiting for session.ready first would deadlock.
            await agent.send(json.dumps({"type": "session.update", "session": self.session_config()}))

            pumps = asyncio.gather(self._pump_twilio(), self._pump_agent())
            silence = asyncio.create_task(self._watch_for_silence())
            unanswered = asyncio.create_task(self._give_up.wait())
            try:
                await asyncio.wait(
                    {pumps, unanswered}, return_when=asyncio.FIRST_COMPLETED
                )
            except (WebSocketDisconnect, ConnectionClosed):
                pass
            finally:
                for task in (silence, unanswered):
                    task.cancel()
                pumps.cancel()
                self._agent = None

    async def _pump_twilio(self) -> None:
        try:
            while True:
                event = json.loads(await self.websocket.receive_text())
                kind = event.get("event")
                if kind == "start":
                    self.stream_sid = event["start"]["streamSid"]
                    await self.on_start(event["start"])
                elif kind == "media":
                    # Audio only counts once the agent session is live.
                    if not self.ready.is_set():
                        continue
                    await self._agent.send(
                        json.dumps({"type": "input.audio", "audio": event["media"]["payload"]})
                    )
                elif kind == "stop":
                    break
        except WebSocketDisconnect:
            logger.info("[%s] Twilio websocket disconnected", self.label)
        except ConnectionClosed:
            logger.info("[%s] Agent websocket closed while reading Twilio", self.label)

    async def _pump_agent(self) -> None:
        async for raw in self._agent:
            message = json.loads(raw)
            kind = message.get("type")

            if kind == "session.ready":
                self.ready.set()
                await self.on_ready()

            elif kind == "reply.started":
                was_speaking = self._agent_speaking.is_set()
                self._agent_speaking.set()
                self._agent_quiet.clear()
                if not was_speaking:
                    await self.on_speaking(True)

            elif kind == "reply.audio":
                # "data" here, not "audio" - the reverse of input.audio.
                self._agent_speaking.set()
                self._agent_quiet.clear()
                await self._send_media(message["data"])

            elif kind == "reply.done":
                was_speaking = self._agent_speaking.is_set()
                self._agent_speaking.clear()
                self._agent_quiet.set()
                if was_speaking:
                    await self.on_speaking(False)
                if message.get("status") == "interrupted":
                    await self._clear_twilio_buffer()
                    self._pending_tool_results.clear()
                    await self.on_interrupted()
                else:
                    while self._pending_tool_results:
                        await self._agent.send(json.dumps(self._pending_tool_results.pop(0)))

            elif kind == "transcript.user":
                if text := (message.get("transcript") or "").strip():
                    # Logged because a call that hangs up on its own is
                    # impossible to diagnose without knowing whether the agent
                    # was hearing anything at all.
                    logger.info("[%s] Heard: %s", self.label, text[:90])
                    self._heard_something.set()
                    await self.on_transcript("them", text)

            elif kind == "transcript.agent":
                if text := (message.get("transcript") or "").strip():
                    await self.on_transcript("us", text)

            elif kind == "tool.call":
                result = await self.on_tool_call(message["name"], message.get("arguments") or {})
                self._pending_tool_results.append(
                    {"type": "tool.result", "call_id": message["call_id"], "result": result}
                )

            elif kind == "error":
                logger.error("[%s] Voice Agent API error: %s", self.label, message)
