"use client";

import { useEffect, useState } from "react";
import { LogoMark } from "@/components/logo-mark";

const SESSION_KEY = "orion-splash-seen";

/**
 * A once-per-session opening, gated by sessionStorage so it plays on first
 * arrival and never again for the rest of that browser session - navigating
 * back to "/" from the dashboard does not replay it.
 *
 * Two distinct beats rather than one shared fade: the mark enters blurred and
 * rotated and settles, a line of type follows it in, then on the way out the
 * mark leaves first - scaling past full size and blurring away - before the
 * backdrop dims behind it.
 */
export function SplashIntro() {
  const [visible, setVisible] = useState(false);
  const [lineVisible, setLineVisible] = useState(false);
  const [markExiting, setMarkExiting] = useState(false);
  const [backdropExiting, setBackdropExiting] = useState(false);

  useEffect(() => {
    let alreadySeen = true;
    try {
      alreadySeen = sessionStorage.getItem(SESSION_KEY) === "1";
    } catch {
      // Storage unavailable (private window, blocked cookies). Skip rather
      // than risk an overlay that never clears.
      alreadySeen = true;
    }
    if (alreadySeen) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    try {
      sessionStorage.setItem(SESSION_KEY, "1");
    } catch {
      // Worst case it plays again next load.
    }

    const timers = [
      window.setTimeout(() => setVisible(true), 0),
      window.setTimeout(() => setLineVisible(true), 820),
      window.setTimeout(() => setMarkExiting(true), 1850),
      window.setTimeout(() => setBackdropExiting(true), 2250),
      window.setTimeout(() => setVisible(false), 2900),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, []);

  if (!visible) return null;

  return (
    <div
      aria-hidden="true"
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center gap-7 bg-[var(--l-bg)] transition-opacity duration-[650ms] ${
        backdropExiting ? "opacity-0" : "opacity-100"
      }`}
    >
      <span className={markExiting ? "animate-mark-out" : "animate-mark-in"}>
        <LogoMark className="h-20 w-20 text-[var(--l-accent)]" />
      </span>
      <p
        className={`font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--l-muted)] ${
          lineVisible ? "animate-fade-rise" : "opacity-0"
        }`}
      >
        The phone call you never make
      </p>
    </div>
  );
}
