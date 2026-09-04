"use client";

import { useEffect, useState } from "react";
import { Phone } from "lucide-react";
import {
  ApiError,
  getCapabilities,
  getNegotiation,
  hangUpCall,
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
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [answeredAt, setAnsweredAt] = useState<string | null>(null);
  const [hangingUp, setHangingUp] = useState(false);

  /** End the call, not just the window.
   *
   * Closing the screen used to leave the call running - billing by the minute,
   * with the agent still talking to the provider and no way to stop it. The
   * screen closes either way, because a customer who pressed End should not be
   * held there by a failed request. */
  async function endCall() {
    // A double-tap would otherwise fire two hangups; the second races the
    // first and reports a failure for a call that is already down.
    if (hangingUp) return;
    setHangingUp(true);
    try {
      const updated = await hangUpCall(session.task_id);
      onPlaced(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHangingUp(false);
      setScreenOpen(false);
    }
  }

  // Ring only while it is actually ringing.
  useRingback(screenOpen && callState === "ringing");

  useEffect(() => {
    if (!screenOpen) return;

    // The call's own progress arrives on the same stream as the transcript.
    // Without it the screen had no way to know the far end had hung up, so it
    // sat there showing a live call that had already ended.
    const stop = subscribeToNegotiationEvents(session.task_id, (event) => {
      if (event.type === "speaking") {
        setAgentSpeaking(event.who === "orion");
      } else if (event.type === "turn") {
        // A transcript arrives after the words, so it is a fallback for the
        // explicit signal rather than the source of truth.
        setAgentSpeaking(event.speaker === "orion");
      } else if (event.type === "call_status") {
        const next = SCREEN_STATE[event.status];
        if (next) setCallState(next);
        if (ENDED.has(event.status)) setNote(ENDED_NOTE[event.status] ?? null);
      } else if (event.type === "status" && event.status === "call_ended") {
        setCallState("ended");
      }
    });
    return stop;
  }, [screenOpen, session.task_id]);

  // The authoritative end-of-call signal.
  //
  // The event feed is not one. It runs through a serverless function that the
  // platform cuts well before a phone call is over, so it reconnects
  // repeatedly mid-call, and a screen that only listens to it can sit showing
  // a live call long after the far end hung up - which is exactly what
  // happened. The negotiation's own status is written by Twilio's webhook and
  // survives any number of dropped streams, so the screen asks for it.
  useEffect(() => {
    if (!screenOpen) return;
    if (callState === "ended" || callState === "error") return;

    let cancelled = false;
    const poll = setInterval(async () => {
      try {
        const current = await getNegotiation(session.task_id);
        if (cancelled) return;

        // answered_at, never status. `status` is CALLING from the moment
        // dialling is accepted as well as on answer, so reading it as
        // "answered" started the timer while the phone was still ringing.
        const ended = current.status === "completed" || current.status === "failed";
        if (ended) {
          setCallState(current.status === "completed" ? "ended" : "error");
          onPlaced(current);
        } else if (current.answered_at) {
          setCallState((s) => (s === "active" ? s : "active"));
          setAnsweredAt(current.answered_at);
        }
        // Otherwise it is still dialling or ringing, and the live feed's
        // call_status events say which.
      } catch {
        // A failed poll is not evidence the call ended; try again.
      }
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [screenOpen, callState, session.task_id, onPlaced]);

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

  // A call can be retried as often as needed. The first attempt frequently
  // reaches nobody - a busy line, no answer, a menu that goes nowhere - and
  // the remedy for all of those is to call again, which used to be impossible
  // because the button disabled itself permanently after one attempt.
  const inProgress = session.status === "calling";
  const attempted = session.status === "failed" || session.status === "completed";

  const blockers: string[] = [];
  // A worked example is not callable at all. Its provider number is real and
  // its bill is invented, so the panel says so rather than offering a button
  // the backend will refuse.
  if (session.is_sample) blockers.push("this is a worked example, not a real bill");
  if (!session.authorized) blockers.push("you haven't authorised Orion to call yet");
  if (hasTwilio === false) blockers.push("no phone line is connected to this deployment");
  if (inProgress) blockers.push("a call is already in progress");

  const canCall = blockers.length === 0;

  async function call() {
    setCalling(true);
    setError(null);
    try {
      const updated = await placeCall(session.task_id);
      onPlaced(updated);
      setCallState("connecting");
      setNote(null);
      setAnsweredAt(null);
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
    <section className="rounded-lg border border-line bg-surface p-6 sm:p-7">
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
        {calling
          ? "Dialling…"
          : inProgress
            ? "Call in progress"
            : attempted
              ? "Call again"
              : "Place the call"}
      </button>

      {attempted && canCall && (
        <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
          {session.outcome
            ? `Last attempt: ${session.outcome}`
            : "This negotiation has been called before. Calling again is fine."}
        </p>
      )}

      {session.is_sample && (
        <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
          Examples are here to show what a finished negotiation looks like. Upload one of your own
          bills to place a real call.
        </p>
      )}

      {!canCall && !inProgress && !session.is_sample && (
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
        answeredAt={answeredAt}
        agentSpeaking={agentSpeaking}
        detail={note}
        muted={false}
        volume={1}
        onToggleMute={() => {}}
        onCycleVolume={() => {}}
        onEnd={endCall}
      />
    </section>
  );
}
