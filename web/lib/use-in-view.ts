"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Fires once when an element first enters the viewport, and then stops
 * observing. Drives the landing page's scroll reveals.
 *
 * One-shot rather than continuous: a section that re-animates every time it
 * scrolls back into view reads as twitchy, and the reveal has already done
 * its job the first time. Where IntersectionObserver is unavailable the
 * content is simply shown, because a reveal that never fires is a blank page.
 */
export function useInView<T extends HTMLElement>(threshold = 0.2) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, inView };
}
