"use client";

import { useEffect, useRef, useState } from "react";
import { Mic } from "lucide-react";
import { BrowserAgentCall, type AgentStatus } from "@/lib/browser-agent";
import { CallScreen, type CallScreenState } from "./call-screen";


/** Talk to the negotiation agent from the browser.
 *
 * Twilio's trial tier blocks the <Stream> verb, so a free account has no phone
 * path at all. This is the same AssemblyAI agent - same prompt, same tools,
 * same playbooks - listening to your microphone instead of a phone line, which
 * makes it a genuine rehearsal of the negotiation before any money is spent on
 * telephony.
 */
const SCREEN_STATE: Record<AgentStatus, CallScreenState> = {
  idle: "idle",
  connecting: "connecting",
  listening: "active",
  speaking: "active",
  ended: "ended",
  error: "error",
};

export function BrowserCall({ taskId, contact }: { taskId: string; contact: string }) {
  const [status, setStatus] = useState<AgentStatus>("idle");
  const [detail, setDetail] = useState<string | null>(null);
  const [turns, setTurns] = useState<{ speaker: "orion" | "rep"; text: string }[]>([]);
  const [tools, setTools] = useState<{ name: string; result: string }[]>([]);
  const [callOpen, setCallOpen] = useState(false);
  const [muted, setMuted] = useState(false);
  // 0 silent, 1 normal, 2 speaker - cycled by the one volume control.
  const [volume, setVolume] = useState(1);
  const callRef = useRef<BrowserAgentCall | null>(null);

  // A live agent session bills for as long as it is open, so never leave one
  // running behind a closed tab.
  useEffect(() => {
    return () => {
      void callRef.current?.stop();
      callRef.current = null;
    };
  }, []);

  function toggleMute() {
    setMuted((was) => {
      const next = !was;
      callRef.current?.setMuted(next);
      return next;
    });
  }

  function cycleVolume() {
    setVolume((was) => {
      const next = was === 0 ? 1 : was === 1 ? 2 : 0;
      callRef.current?.setVolume(next);
      return next;
    });
  }

  async function begin() {
    setTurns([]);
    setTools([]);
    setDetail(null);
    setMuted(false);
    setVolume(1);
    setCallOpen(true);
    const call = new BrowserAgentCall(taskId, {
      onStatus: (next, why) => {
        setStatus(next);
        if (why) setDetail(why);
        // The agent hangs up on its own after an unanswered silence; the screen
        // should not be left behind when it does.
        if (next === "ended") setCallOpen(false);
      },
      onTranscript: (speaker, text) => setTurns((prev) => [...prev, { speaker, text }]),
      onTool: (name, _args, result) => setTools((prev) => [...prev, { name, result }]),
    });
    callRef.current = call;
    try {
      await call.start();
    } catch (error) {
      // start() can fail after the context and mic are open - blocked
      // permissions, a refused token - so release whatever it did acquire.
      void call.stop();
      callRef.current = null;
      setCallOpen(false);
      setStatus("error");
      setDetail(
        error instanceof Error && error.name === "NotAllowedError"
          ? "Microphone access was blocked."
          : error instanceof Error
            ? error.message
            : String(error)
      );
    }
  }

  async function end() {
    // Both pieces of UI state are set here rather than waiting on stop() to
    // report back. Pressing End should leave the call immediately, and if
    // teardown misbehaves the button must not be left saying the call is still
    // running - which is exactly what happened when this trusted stop().
    setCallOpen(false);
    setStatus("ended");
    const call = callRef.current;
    callRef.current = null;
    await call?.stop();
  }

  const live = status === "listening" || status === "speaking" || status === "connecting";

  return (
    <section className="rounded-lg border border-line bg-surface p-5 sm:p-7">
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
          Rehearse the call
        </p>
        <h2 className="mt-3 font-display text-[1.375rem] leading-snug text-ink sm:text-[1.5375rem]">
          Talk to Orion before it talks to them
        </h2>
        <p className="mt-3 max-w-prose text-[14px] leading-relaxed text-ink-soft">
          The same agent, on your microphone. Play the rep and hear it negotiate.
        </p>
      </div>

      <button
        type="button"
        onClick={begin}
        disabled={live}
        className="mt-7 flex items-center gap-2 rounded bg-accent px-5 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
      >
        <Mic size={16} />
        {live ? "Call in progress" : "Start rehearsal"}
      </button>

      <CallScreen
        open={callOpen}
        contact={contact}
        subtitle="Rehearsal · your microphone"
        state={SCREEN_STATE[status]}
        agentSpeaking={status === "speaking"}
        muted={muted}
        volume={volume}
        onToggleMute={toggleMute}
        onCycleVolume={cycleVolume}
        onEnd={end}
        detail={detail}
      />

      {turns.length > 0 && (
        <div className="mt-6 max-h-80 space-y-4 overflow-y-auto border-t border-line pt-6">
          {turns.map((turn, index) => (
            <div key={index} className={turn.speaker === "orion" ? "text-right" : ""}>
              <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                {turn.speaker === "orion" ? "Orion" : "You"}
              </p>
              <p className="mt-1 text-[14px] leading-relaxed text-ink">{turn.text}</p>
            </div>
          ))}
        </div>
      )}

      {tools.length > 0 && (
        <ul className="mt-6 space-y-2 border-t border-line pt-6">
          {tools.map((tool, index) => (
            <li key={index} className="border-l-2 border-accent pl-3 text-[13px] text-ink-soft">
              <span className="font-mono text-[11px] text-accent">{tool.name}</span> - {tool.result}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
