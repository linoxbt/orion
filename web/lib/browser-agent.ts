import { createBrowserSession, recordAgentTranscript, runAgentTool } from "./api";

/** Runs an AssemblyAI Voice Agent session over the browser's microphone.
 *
 * Twilio's trial tier blocks the <Stream> verb, so there is no phone path on a
 * free account. The Voice Agent API deploys to a browser just as readily, so
 * this is the same agent - same prompt, same tools, same playbooks - with a
 * microphone where the phone line would be.
 *
 * Audio here is the API's default (24kHz PCM16, base64 inside JSON events),
 * not Twilio's 8kHz mu-law. Two details worth knowing:
 *   - Audio going TO the agent travels in "audio"; audio coming BACK travels
 *     in "data". The asymmetry is easy to miss and fails silently.
 *   - Nothing may be sent before session.ready, so the mic is gated on it.
 */

const AGENTS_WS = "wss://agents.assemblyai.com/v1/ws";
const SAMPLE_RATE = 24000;
// How long to let a closing line finish playing before the session is closed.
// The same beat the phone path leaves for a goodbye.
const GOODBYE_MS = 3000;

/** What a person does when the other end goes quiet.
 *
 * The Voice Agent API has no no-input timeout: it waits for a user utterance,
 * so if nobody ever speaks after the greeting, no turn ever ends and the agent
 * stays silent forever. A real caller doesn't do that - they check you're
 * still there, try once more, then hang up. `reply.create` is the documented
 * way to make the agent speak without a user utterance triggering it.
 *
 * It also matters commercially: the docs are explicit that idle time on an
 * open session is billed, so silence has to end the call eventually rather
 * than sit there costing money. */
const SILENCE_PROMPTS: { after: number; instructions: string | null }[] = [
  {
    after: 12000,
    instructions:
      "You have had no response for several seconds. Politely check whether the person is " +
      "still there - for example 'Hello, are you still there?' - and keep it to one short line.",
  },
  {
    after: 15000,
    instructions:
      "Still no response. Say once more that you can't hear anything and ask them to speak up " +
      "if they are there. One short line.",
  },
  {
    after: 20000,
    instructions:
      "There has been no response at all. Say politely that you'll try again another time, " +
      "thank them, and say goodbye. One short line.",
  },
];

export type AgentStatus = "idle" | "connecting" | "listening" | "speaking" | "ended" | "error";

/** The subset of Voice Agent API server events this client acts on. Everything
 * else is ignored, so unknown future event types are harmless. */
interface AgentMessage {
  type: string;
  /** reply.audio carries base64 audio in "data" - not "audio", which is the
   * field name going the other way. */
  data?: string;
  transcript?: string;
  status?: string;
  name?: string;
  call_id?: string;
  arguments?: Record<string, unknown>;
  error?: string;
}

export interface AgentCallbacks {
  onStatus?: (status: AgentStatus, detail?: string) => void;
  onTranscript?: (speaker: "orion" | "rep", text: string, final: boolean) => void;
  onTool?: (name: string, args: Record<string, unknown>, result: string) => void;
}

// An AudioWorklet is the only way to get raw PCM out of the mic; it ships as a
// blob so there's no separate public asset to keep in sync.
const CAPTURE_WORKLET = `
class CaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel && channel.length) this.port.postMessage(new Float32Array(channel));
    return true;
  }
}
registerProcessor('capture', CaptureProcessor);
`;

function floatToPcm16Base64(samples: Float32Array): string {
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]!));
    pcm[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]!);
  return btoa(binary);
}

function base64ToFloat32(b64: string): Float32Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const pcm = new Int16Array(bytes.buffer);
  const out = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i]! / 0x8000;
  return out;
}

export class BrowserAgentCall {
  private ws: WebSocket | null = null;
  private audio: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private ready = false;
  /** Absolute AudioContext time the next reply chunk should start at, so
   * consecutive chunks butt up against each other instead of overlapping. */
  private playhead = 0;
  private playing: AudioBufferSourceNode[] = [];
  private pendingTools: { type: string; call_id: string; result: string }[] = [];
  /** Output gain, so volume and speaker mode are real rather than cosmetic. */
  private gain: GainNode | null = null;
  private micMuted = false;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;
  private silenceStage = 0;
  /** stop() can arrive from the End button, the socket closing, and the
   * unanswered-silence timer at once; it should only run through once. */
  private stopped = false;

  constructor(
    private taskId: string,
    private callbacks: AgentCallbacks = {}
  ) {}

  private status(status: AgentStatus, detail?: string) {
    this.callbacks.onStatus?.(status, detail);
  }

  async start(): Promise<void> {
    this.status("connecting");

    const { token, session } = await createBrowserSession(this.taskId);

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });

    this.audio = new AudioContext({ sampleRate: SAMPLE_RATE });
    // Everything the agent says goes through here, so volume and speaker mode
    // change what you actually hear instead of just toggling an icon.
    this.gain = this.audio.createGain();
    this.gain.connect(this.audio.destination);
    await this.audio.audioWorklet.addModule(
      URL.createObjectURL(new Blob([CAPTURE_WORKLET], { type: "application/javascript" }))
    );

    this.ws = new WebSocket(`${AGENTS_WS}?token=${encodeURIComponent(token)}`);

    this.ws.onopen = () => {
      // Configuration goes up front; waiting for session.ready would deadlock.
      this.ws?.send(JSON.stringify({ type: "session.update", session }));
    };

    this.ws.onmessage = (event) => this.handleMessage(JSON.parse(event.data));

    this.ws.onerror = () => {
      // Surface the failure, then tear down - an errored socket is not a call
      // anyone can continue, and leaving it open keeps billing.
      this.status("error", "connection failed");
      // Keep the error visible rather than replacing it with a bland "ended".
      void this.stop("error");
    };
    this.ws.onclose = () => {
      this.ready = false;
      // The far end can drop the call too, so this is a real ending - but
      // stop() may already have announced it.
      if (!this.stopped) void this.stop();
    };

    const source = this.audio.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.audio, "capture");
    this.node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      // Audio only counts once the agent session is live. Mute drops the
      // frames here rather than lowering a gain, so nothing reaches the agent
      // at all - muting a call should mean the other side hears silence, not
      // quiet speech.
      if (this.micMuted) return;
      if (!this.ready || this.ws?.readyState !== WebSocket.OPEN) return;
      this.ws.send(
        JSON.stringify({ type: "input.audio", audio: floatToPcm16Base64(event.data) })
      );
    };
    source.connect(this.node);
    // Keeps the worklet pulling without routing the mic to the speakers.
    this.node.connect(this.audio.destination);
  }

  private async handleMessage(message: AgentMessage) {
    switch (message.type) {
      case "session.ready":
        this.ready = true;
        this.status("listening");
        // Deliberately no countdown yet: the greeting is about to play, and
        // nobody is being silent while the agent is still talking.
        break;

      case "reply.started":
        // The agent has the floor - stop counting against the other side.
        this.clearSilenceTimer();
        this.status("speaking");
        break;

      case "reply.audio":
        // "data" here, not "audio" - the reverse of input.audio.
        this.enqueue(base64ToFloat32(message.data ?? ""));
        this.status("speaking");
        break;

      case "reply.done":
        if (message.status === "interrupted") this.flush();
        this.status("listening");
        // Only now does the other side owe a reply, so only now does the clock
        // start. Starting it any earlier is what made the agent interrupt its
        // own greeting.
        this.scheduleSilenceCheck();
        while (this.pendingTools.length) {
          this.ws?.send(JSON.stringify(this.pendingTools.shift()));
        }
        break;

      case "transcript.user": {
        const text = (message.transcript ?? "").trim();
        // Somebody spoke, so the call is alive. Drop the countdown entirely and
        // reset the ladder - it re-arms when the agent next finishes a turn.
        if (text) {
          this.clearSilenceTimer();
          this.silenceStage = 0;
        }
        if (text) {
          this.callbacks.onTranscript?.("rep", text, true);
          void recordAgentTranscript(this.taskId, "rep", text);
        }
        break;
      }

      case "transcript.agent": {
        const text = (message.transcript ?? "").trim();
        if (text) {
          this.callbacks.onTranscript?.("orion", text, true);
          void recordAgentTranscript(this.taskId, "orion", text);
        }
        break;
      }

      case "tool.call": {
        // Run tools on the server, not here: they write to the real session and
        // read the encrypted vault, so their values never touch browser code.
        const args = message.arguments ?? {};
        let result = "That didn't work.";
        try {
          result = (await runAgentTool(this.taskId, message.name ?? "", args)).result;
        } catch {
          // Fall through with the default; a failed tool must not end the call.
        }
        this.callbacks.onTool?.(message.name ?? "", args, result);
        this.pendingTools.push({
          type: "tool.result",
          call_id: message.call_id ?? "",
          result,
        });
        // The agent decided the conversation is finished. On a phone call the
        // line is hung up; here the session is what costs money for as long as
        // it stays open, and it used to stay open until the silence ladder ran
        // out or somebody pressed End. Long enough for the goodbye to play.
        if (message.name === "end_call") {
          setTimeout(() => void this.stop(), GOODBYE_MS);
        }
        break;
      }

      case "error":
        this.status("error", message.error ?? "unknown");
        break;
    }
  }

  private enqueue(samples: Float32Array) {
    if (!this.audio) return;
    const buffer = this.audio.createBuffer(1, samples.length, SAMPLE_RATE);
    // Write through the channel's own array: copyToChannel is typed against
    // Float32Array<ArrayBuffer>, and one built from a decoded base64 buffer is
    // Float32Array<ArrayBufferLike>.
    buffer.getChannelData(0).set(samples);

    const source = this.audio.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gain ?? this.audio.destination);

    const now = this.audio.currentTime;
    // A playhead that has fallen behind wall-clock means playback drained;
    // restart from now rather than scheduling in the past.
    this.playhead = Math.max(this.playhead, now);
    source.start(this.playhead);
    this.playhead += buffer.duration;

    this.playing.push(source);
    source.onended = () => {
      this.playing = this.playing.filter((s) => s !== source);
    };
  }

  /** Drop everything queued - the human talked over the agent. */
  private flush() {
    for (const source of this.playing) {
      try {
        source.stop();
      } catch {
        // Already finished.
      }
    }
    this.playing = [];
    this.playhead = this.audio?.currentTime ?? 0;
  }

  /** True mute: the microphone stops reaching the agent entirely. */
  setMuted(muted: boolean): void {
    this.micMuted = muted;
  }

  /** 1 is normal, higher is "speaker". Clamped, because a gain of 4 on a
   * laptop speaker is distortion, not volume. */
  setVolume(level: number): void {
    if (!this.gain || !this.audio) return;
    const clamped = Math.max(0, Math.min(2.5, level));
    this.gain.gain.setTargetAtTime(clamped, this.audio.currentTime, 0.02);
  }

  private clearSilenceTimer() {
    if (this.silenceTimer) clearTimeout(this.silenceTimer);
    this.silenceTimer = null;
  }

  private scheduleSilenceCheck() {
    this.clearSilenceTimer();
    const step = SILENCE_PROMPTS[this.silenceStage];
    if (!step) return;

    this.silenceTimer = setTimeout(() => {
      if (!this.ready || this.ws?.readyState !== WebSocket.OPEN) return;

      const isLast = this.silenceStage === SILENCE_PROMPTS.length - 1;
      // reply.create makes the agent speak without a user utterance - the
      // documented way to break a silence the API would otherwise wait out
      // forever.
      this.ws.send(
        JSON.stringify({ type: "reply.create", instructions: step.instructions })
      );
      this.callbacks.onStatus?.("speaking", isLast ? "no response - ending" : undefined);

      this.silenceStage += 1;
      // The next prompt is armed by reply.done when this one finishes speaking,
      // not here - otherwise the ladder runs while the agent is mid-sentence.
      if (isLast) {
        // Idle sessions are billed, so an unanswered call has to end rather
        // than sit open. Long enough for the goodbye to finish playing.
        setTimeout(() => void this.stop(), 8000);
      }
    }, step.after);
  }

  /** End the call and release everything.
   *
   * Every step is isolated, because teardown used to run as one unbroken
   * sequence with the status update last: anything that threw part-way - and
   * closing an already-closed AudioContext does - skipped the rest. That left
   * the UI believing the call was still running, and worse, left the
   * microphone live and the websocket open, which is a billable session
   * nobody is watching.
   *
   * So: the call is over the moment this is called, and every release is
   * attempted regardless of what failed before it.
   */
  async stop(finalStatus: AgentStatus = "ended"): Promise<void> {
    if (this.stopped) return;
    this.stopped = true;
    this.ready = false;

    // Announce first. UI state must never be hostage to teardown succeeding.
    this.status(finalStatus);

    const release = async (what: string, fn: () => unknown) => {
      try {
        await fn();
      } catch (error) {
        // Nothing here is worth surfacing - the call has already ended.
        console.warn(`[orion] releasing ${what} failed`, error);
      }
    };

    await release("silence timer", () => this.clearSilenceTimer());
    await release("playback", () => this.flush());
    await release("capture node", () => this.node?.disconnect());
    // The microphone matters most: leaving it live keeps the browser's
    // recording indicator on after the user has hung up.
    await release("microphone", () =>
      this.stream?.getTracks().forEach((track) => track.stop())
    );
    await release("socket", () => {
      if (this.ws && this.ws.readyState <= WebSocket.OPEN) this.ws.close();
    });
    await release("audio context", async () => {
      if (this.audio && this.audio.state !== "closed") await this.audio.close();
    });

    this.node = null;
    this.stream = null;
    this.ws = null;
    this.audio = null;
    this.gain = null;
  }
}
