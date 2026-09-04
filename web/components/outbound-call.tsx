"use client";

import { useEffect, useState } from "react";
import { Phone } from "lucide-react";
import {
  ApiError,
  getCapabilities,
  placeCall,
  subscribeToNegotiationEvents,
  type NegotiationSession,
} from "@/lib/api";
import { CallScreen, type CallScreenState } from "./call-screen";
import { useRingback } from "./use-ringback";

/** Twilio's CallStatus, mapped to what the screen should show.
 *
 * Only "in-progress" means somebody actually answered, and it is the only one
 * that starts the timer.
 */
const SCREEN_STATE: Record<string, CallScreenState> = {
  queued: "connecting",
  initiated: "connecting",
  ringing: "ringing",
  "in-progress": "active",
  completed: "ended",
  busy: "ended",
  "no-answer": "ended",
  canceled: "ended",
  failed: "error",
};

const ENDED = new Set(["completed", "busy", "no-answer", "canceled", "failed"]);

const ENDED_NOTE: Record<string, string> = {
  busy: "The line was busy.",
  "no-answer": "Nobody answered.",
  failed: "The call could not be connected.",
  canceled: "The call was cancelled before it connected.",
};

/** Placing the real outbound call.
 *
 * This panel is always rendered, even when the call can't be placed. Hiding it
 * until every precondition was met meant the button simply didn't exist and
 * there was no way to tell why - you could only see the rehearsal and had to
 * guess whether Twilio, consent, or something else was missing. Showing it
 * disabled, with the reason, answers that in the UI.
 */
export function OutboundCall({
  session,
  onPlaced,
}: {
  session: NegotiationSession;
  onPlaced: (updated: NegotiationSession) => void;
}) {
  const [hasTwilio, setHasTwilio] = useState<boolean | null>(null);
  const [calling, setCalling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [screenOpen, setScreenOpen] = useState(false);
  // Driven by Twilio, not by the fact that dialling was accepted.
  const [callState, setCallState] = useState<CallScreenState>("connecting");
  const [note, setNote] = useState<string | null>(null);

  // Ring only while it is actually ringing.
  useRingback(screenOpen && callState === "ringing");

  useEffect(() => {
    if (!screenOpen) return;

    // The call's own progress arrives on the same stream as the transcript.
    // Without it the screen had no way to know the far end had hung up, so it
    // sat there showing a live call that had already ended.
    const stop = subscribeToNegotiationEvents(session.task_id, (event) => {
      if (event.type === "call_status") {
        const next = SCREEN_STATE[event.status];
        if (next) setCallState(next);
        if (ENDED.has(event.status)) setNote(ENDED_NOTE[event.status] ?? null);
      } else if (event.type === "status" && event.status === "call_ended") {
        setCallState("ended");
      }
    });
    return stop;
  }, [screenOpen, session.task_id]);

  // Once it is over, close the screen rather than leaving a dead call on top
  // of the page.
  useEffect(() => {
    if (callState !== "ended" && callState !== "error") return;
    const timer = setTimeout(() => setScreenOpen(false), 2500);
    return () => clearTimeout(timer);
  }, [callState]);

  useEffect(() => {
    getCapabilities()
      .then((h) => setHasTwilio(Boolean(h.capabilities.hasTwilio)))
      .catch(() => setHasTwilio(null));
  }, []);

  const alreadyCalled = session.status !== "pending";
  const blockers: string[] = [];
  if (!session.authorized) blockers.push("you haven't authorised Orion to call yet");
  if (hasTwilio === false) blockers.push("no phone line is connected to this deployment");
  if (alreadyCalled) blockers.push("this negotiation has already been called");

  const canCall = blockers.length === 0;

  async function call() {
    setCalling(true);
    setError(null);
    try {
      const updated = await placeCall(session.task_id);
      onPlaced(updated);
      setCallState("connecting");
      setNote(null);
      setScreenOpen(true);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "";
      // A 422 carries Twilio's own explanation of why it refused, which is
      // far more use than a generic failure - the first one most people hit
      // is dialling a country the account has not enabled.
      setError(
        detail === "twilio_not_configured"
          ? "No phone line is connected, so the call can't be dialled."
          : detail === "not_authorized"
            ? "Authorise Orion above first."
            : detail
              ? detail
              : err instanceof Error
                ? err.message
                : String(err)
      );
    } finally {
      setCalling(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-line bg-surface p-7">
      <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
        The real call
      </p>
      <h2 className="mt-3 font-display text-[1.5375rem] leading-snug text-ink">
        Have Orion call {session.provider}
      </h2>
      <p className="mt-3 max-w-prose text-[14px] leading-relaxed text-ink-soft">
        Dials {session.phone_number} and holds the negotiation for you. The call is recorded, and
        the outcome is read back from that recording before anything is charged.
      </p>

      <button
        type="button"
        onClick={call}
        disabled={!canCall || calling}
        className="mt-6 flex items-center gap-2 rounded bg-accent px-5 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
      >
        <Phone size={16} />
        {calling ? "Dialling…" : alreadyCalled ? "Already called" : "Place the call"}
      </button>

      {!canCall && !alreadyCalled && (
        <p className="mt-4 max-w-prose text-[13px] leading-relaxed text-ink-soft">
          Not available yet because {blockers.join(", and ")}.
          {hasTwilio === false && (
            <>
              {" "}
              Everything else works without it - the rehearsal above runs the same agent over your
              microphone.
            </>
          )}
        </p>
      )}

      {error && <p className="mt-4 text-[13px] text-fail">{error}</p>}

      <CallScreen
        open={screenOpen}
        contact={session.provider}
        subtitle={session.phone_number}
        state={callState}
        detail={note}
        muted={false}
        volume={1}
        onToggleMute={() => {}}
        onCycleVolume={() => {}}
        onEnd={() => setScreenOpen(false)}
      />
    </section>
  );
}
