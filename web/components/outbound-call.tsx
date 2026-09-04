"use client";

import { useEffect, useState } from "react";
import { Phone } from "lucide-react";
import { ApiError, getCapabilities, placeCall, type NegotiationSession } from "@/lib/api";
import { CallScreen } from "./call-screen";

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
        state={session.status === "calling" ? "active" : "connecting"}
        muted={false}
        volume={1}
        onToggleMute={() => {}}
        onCycleVolume={() => {}}
        onEnd={() => setScreenOpen(false)}
      />
    </section>
  );
}
