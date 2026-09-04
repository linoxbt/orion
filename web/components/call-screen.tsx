"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Mic, MicOff, PhoneOff, Volume1, Volume2, VolumeX } from "lucide-react";
import { LogoMark } from "./logo-mark";

export type CallScreenState =
  | "idle"
  | "connecting"
  | "ringing"
  | "active"
  | "ended"
  | "error";

export interface CallScreenProps {
  open: boolean;
  /** Who is being called - the provider, as it would show on a handset. */
  contact: string;
  /** The number dialled, or a note like "Rehearsal" when there is no line. */
  subtitle: string;
  state: CallScreenState;
  /** True while the agent is talking, so you can see who has the floor. */
  agentSpeaking?: boolean;
  /** When the far end actually picked up, ISO 8601. The timer is anchored to
   *  this rather than to when this screen noticed, so it stays correct across
   *  a reconnect or a refresh mid-call. */
  answeredAt?: string | null;
  muted: boolean;
  /** 0 silent, 1 normal, 2 speaker. */
  volume: number;
  onToggleMute: () => void;
  onCycleVolume: () => void;
  onEnd: () => void;
  detail?: string | null;
  children?: React.ReactNode;
}

const STATE_LABEL: Record<CallScreenState, string> = {
  idle: "Ready",
  connecting: "Connecting…",
  ringing: "Ringing…",
  active: "",
  ended: "Call ended",
  error: "Call failed",
};

/** Time since the call was answered.
 *
 * `running` must be true only once the far end actually picks up. It used to
 * be true from the moment dialling was accepted, so the timer counted through
 * the ringing and told you a call had lasted twenty seconds when nobody had
 * answered it yet.
 */
function useElapsed(running: boolean, since?: string | null): string {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) {
      setSeconds(0);
      return;
    }
    // Anchored to when the call was actually answered, falling back to now if
    // that is unknown. Incrementing a counter instead would under-count in a
    // backgrounded tab, and starting from "now" would restart the clock on
    // every reconnect.
    const parsed = since ? Date.parse(since) : NaN;
    const startedAt = Number.isFinite(parsed) ? parsed : Date.now();
    setSeconds(0);
    const timer = setInterval(
      () => setSeconds(Math.floor((Date.now() - startedAt) / 1000)),
      500
    );
    return () => clearInterval(timer);
  }, [running, since]);

  const mm = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const ss = (seconds % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}

function ControlButton({
  label,
  active = false,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        aria-pressed={active}
        className={`flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full transition-colors ${
          active ? "bg-white text-black" : "bg-white/10 text-white hover:bg-white/20"
        }`}
      >
        {children}
      </button>
      <span className="text-[11px] text-white/55">{label}</span>
    </div>
  );
}

/** A handset, full screen.
 *
 * Rendered in a portal over everything else rather than inside the page,
 * because a call is a mode: while one is running it is the only thing you are
 * doing, and burying it in a card among forms invites clicking away from a
 * live, billable session. Identical for a rehearsal and a real call, so the
 * two can't drift apart.
 */
export function CallScreen({
  open,
  contact,
  subtitle,
  state,
  agentSpeaking = false,
  answeredAt = null,
  muted,
  volume,
  onToggleMute,
  onCycleVolume,
  onEnd,
  detail,
  children,
}: CallScreenProps) {
  // Ringing is a live call too - the avatar should pulse while it rings.
  const live = state === "active" || state === "connecting" || state === "ringing";
  const elapsed = useElapsed(state === "active", answeredAt);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // A call is a mode, so the page behind it shouldn't scroll.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Escape hangs up. On a live call that is a real action, so it is the only
  // key bound - nothing here dismisses without ending.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onEnd();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onEnd]);

  if (!open || !mounted) return null;

  const VolumeIcon = volume === 0 ? VolumeX : volume > 1 ? Volume2 : Volume1;
  const volumeLabel = volume === 0 ? "Muted" : volume > 1 ? "Speaker" : "Volume";

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Call with ${contact}`}
      className="fixed inset-0 z-[100] flex flex-col bg-gradient-to-b from-[#2b2b2e] to-[#0d0d0f]"
    >
      <div className="flex flex-1 flex-col items-center justify-between px-6 py-14 sm:py-20">
        {/* Callee */}
        <div className="text-center">
          <p className="text-[1.9375rem] font-medium leading-tight text-white sm:text-[2.4375rem]">
            {contact}
          </p>
          <p className="mt-2 text-[14px] text-white/55">{subtitle}</p>
          <p className="tabular mt-6 text-[16px] text-white/70">
            {state === "active" ? elapsed : STATE_LABEL[state]}
          </p>
          {detail && <p className="mt-3 text-[13px] text-[#ff8a80]">{detail}</p>}
        </div>

        {/* Who has the floor */}
        <div className="flex flex-col items-center gap-4" aria-live="polite">
          <span
            className={`flex h-28 w-28 items-center justify-center rounded-full transition-colors ${
              agentSpeaking ? "bg-white/20" : "bg-white/[0.07]"
            }`}
          >
            <span
              className={`flex h-20 w-20 items-center justify-center rounded-full text-[1.6875rem] font-medium ${
                agentSpeaking ? "live-dot bg-white text-black" : "bg-white/10 text-white/70"
              }`}
            >
              {/* Whose voice this is, not merely a highlight. The avatar used
                  to show the company's initial the whole way through and only
                  change shade, so there was nothing to tell you which of the
                  two you were listening to. */}
              {agentSpeaking ? (
                <LogoMark className="h-10 w-10" />
              ) : (
                contact.trim().charAt(0).toUpperCase() || "?"
              )}
            </span>
          </span>
          {state === "active" && (
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">
              {agentSpeaking ? "Orion" : contact}
            </p>
          )}
          <p className="text-[14px] text-white/60">
            {state === "connecting"
              ? "Connecting"
              : state === "ringing"
                ? "Ringing"
                : agentSpeaking
                  ? "Orion is speaking"
                  : state === "active"
                    ? muted
                      ? "Muted - they can’t hear you"
                      : "Listening"
                    : " "}
          </p>
        </div>

        {/* Controls, on one line */}
        <div className="w-full max-w-md">
          <div className="flex items-start justify-center gap-8 sm:gap-12">
            <ControlButton label={muted ? "Unmute" : "Mute"} active={muted} onClick={onToggleMute}>
              {muted ? <MicOff size={26} /> : <Mic size={26} />}
            </ControlButton>

            <ControlButton label={volumeLabel} active={volume > 1} onClick={onCycleVolume}>
              <VolumeIcon size={26} />
            </ControlButton>

            <div className="flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={onEnd}
                aria-label="End call"
                className="flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full bg-[#e5484d] text-white transition-opacity hover:opacity-90"
              >
                <PhoneOff size={26} />
              </button>
              <span className="text-[11px] text-white/55">{live ? "End" : "Close"}</span>
            </div>
          </div>

          {children && <div className="mt-10">{children}</div>}
        </div>
      </div>
    </div>,
    document.body
  );
}
