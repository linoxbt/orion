"use client";

import { useScrollSequence } from "@/lib/use-scroll-sequence";

export interface SequenceItem {
  /** The mono label above the heading: a tool name, or a stage. */
  tag: string;
  title: string;
  body: string;
}

/**
 * Panels pinned in one place, swapping as you scroll.
 *
 * The tall wrapper supplies the scroll distance; the sticky child pins one
 * viewport-height frame; every panel sits absolutely inside it, stacked in the
 * same spot. Scrolling moves through the panels without moving the frame,
 * which is what makes them read as one thing changing rather than a list
 * going past.
 */
export function ScrollSequence({
  eyebrow,
  heading,
  items,
}: {
  eyebrow: string;
  heading: string;
  items: SequenceItem[];
}) {
  const { wrapperRef, panelRefs } = useScrollSequence<HTMLDivElement>(items.length);

  return (
    <section className="relative border-b border-[var(--l-line)]">
      <div className="mx-auto max-w-7xl px-5 pt-20 sm:px-8 lg:pt-24">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--l-accent)]">
          {eyebrow}
        </p>
        <h2 className="mt-5 max-w-2xl text-[2rem] font-medium leading-[1.1] tracking-[-0.025em] text-[var(--l-text)] sm:text-[2.6rem]">
          {heading}
        </h2>
      </div>

      <div ref={wrapperRef} className="relative" style={{ height: `${items.length * 100}vh` }}>
        <div className="sticky top-0 flex h-screen items-center justify-center overflow-hidden">
          {items.map((item, i) => (
            <div
              key={item.tag}
              ref={(el) => {
                panelRefs.current[i] = el;
              }}
              className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center opacity-0"
            >
              <span className="font-mono text-[11px] tracking-[0.2em] text-[var(--l-accent)]">
                {String(i + 1).padStart(2, "0")} / {String(items.length).padStart(2, "0")}
              </span>
              <span className="mt-4 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--l-muted)]">
                {item.tag}
              </span>
              <h3 className="mt-6 max-w-3xl text-[2rem] font-medium leading-[1.08] tracking-[-0.02em] text-[var(--l-text)] sm:text-[3.2rem]">
                {item.title}
              </h3>
              <p className="mt-6 max-w-xl text-[15px] leading-[1.65] text-[var(--l-muted)] sm:text-[17px]">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
