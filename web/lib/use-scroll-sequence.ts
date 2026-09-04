"use client";

import { useEffect, useRef } from "react";

/** How much of a panel's own segment is spent fading in and out. */
const EDGE_FRACTION = 0.12;

/**
 * Drives a pinned scroll sequence: several panels stacked in the same place,
 * one visible at a time, swapping as the page scrolls rather than scrolling
 * past.
 *
 * Progress through the tall wrapper is measured the way a CSS "cover" range
 * would: 0 when its top reaches the bottom of the viewport, 1 when its bottom
 * leaves the top. That is split into equal segments, one per panel, and each
 * panel fades and settles within its own.
 *
 * Styles are written inline inside requestAnimationFrame rather than through
 * React state, so scrolling never triggers a re-render. Under
 * prefers-reduced-motion nothing is bound to scroll at all and every panel is
 * simply left visible.
 */
export function useScrollSequence<T extends HTMLElement>(count: number) {
  const wrapperRef = useRef<T | null>(null);
  const panelRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      panelRefs.current.forEach((panel) => {
        if (panel) {
          panel.style.opacity = "1";
          panel.style.transform = "none";
          panel.style.position = "relative";
        }
      });
      return;
    }

    let ticking = false;

    function update() {
      ticking = false;
      if (!wrapper) return;

      const rect = wrapper.getBoundingClientRect();
      const viewportHeight = window.innerHeight || 1;
      const total = rect.height + viewportHeight;
      const progress = Math.min(1, Math.max(0, (viewportHeight - rect.top) / total));
      const segment = 1 / count;

      panelRefs.current.forEach((panel, i) => {
        if (!panel) return;
        const local = (progress - i * segment) / segment;

        let opacity = 0;
        if (local >= 0 && local <= 1) {
          if (local < EDGE_FRACTION) opacity = local / EDGE_FRACTION;
          else if (local > 1 - EDGE_FRACTION) opacity = (1 - local) / EDGE_FRACTION;
          else opacity = 1;
        }

        panel.style.opacity = String(opacity);
        panel.style.transform =
          `translateY(${24 * (1 - opacity)}px) scale(${0.92 + 0.08 * opacity})`;
        // A fully faded panel must not swallow clicks meant for the one on top.
        panel.style.pointerEvents = opacity > 0.5 ? "auto" : "none";
      });
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [count]);

  return { wrapperRef, panelRefs };
}
