"use client";

import { useInView } from "@/lib/use-in-view";

/**
 * A section that arrives as you reach it.
 *
 * Rendered visible and then animated, never parked at opacity 0 waiting on an
 * observer: if the observer never fires - no JavaScript, an old browser, a
 * screenshot - the content must still be there. The animation is the
 * enhancement, not the thing that makes the page exist.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();

  return (
    <div
      ref={ref}
      className={`${className} ${inView ? "animate-reveal" : ""}`}
      style={inView && delay ? { animationDelay: `${delay}ms`, animationFillMode: "backwards" } : undefined}
    >
      {children}
    </div>
  );
}
