"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Mic, MicOff, PhoneOff, Volume1, Volume2, VolumeX } from "lucide-react";

export type CallScreenState = "idle" | "connecting" | "active" | "ended" | "error";

export interface CallScreenProps {
  open: boolean;
  /** Who is being called - the provider, as it would show on a handset. */
  contact: string;
  /** The number dialled, or a note like "Rehearsal" when there is no line. */
  subtitle: string;
  state: CallScreenState;
  /** True while the agent is talking, so you can see who has the floor. */
  agentSpeaking?: boolean;
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
  connecting: "Calling…",
  active: "",
  ended: "Call ended",
  error: "Call failed",
};

function useElapsed(running: boolean): string {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) {
      setSeconds(0);
      return;
    }
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [running]);

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
  muted,
  volume,
  onToggleMute,
  onCycleVolume,
  onEnd,
  detail,
  children,
}: CallScreenProps) {
  const live = state === "active" || state === "connecting";
  const elapsed = useElapsed(state === "active");
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
              {contact.trim().charAt(0).toUpperCase() || "?"}
            </span>
          </span>
          <p className="text-[14px] text-white/60">
            {state === "connecting"
              ? "Connecting"
              : agentSpeaking
                ? "Orion is speaking"
                : state === "active"
                  ? muted
                    ? "Muted - they can't hear you"
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
