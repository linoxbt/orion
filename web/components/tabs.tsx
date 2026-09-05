"use client";

import { useId, useRef, useState } from "react";

export interface Tab {
  id: string;
  label: string;
  render: () => React.ReactNode;
}

/**
 * A tabbed card.
 *
 * Two of the negotiation page's panels are things you fill in occasionally -
 * the verification answers, and an outcome typed in by hand - and both were
 * always open, so the page you actually read was mostly forms you were not
 * using. Tabs keep them one click away without spending a screen each.
 *
 * The strip scrolls sideways rather than wrapping: three labels fit a phone,
 * a fourth would otherwise push the card into two rows of tabs.
 */
export function Tabs({ tabs, className = "" }: { tabs: Tab[]; className?: string }) {
  const [active, setActive] = useState(tabs[0]?.id);
  const base = useId();
  const strip = useRef<HTMLDivElement>(null);

  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];
  if (!current) return null;

  function onKeyDown(event: React.KeyboardEvent) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const index = tabs.findIndex((tab) => tab.id === current!.id);
    const next = tabs[(index + step + tabs.length) % tabs.length]!;
    setActive(next.id);
    strip.current
      ?.querySelector<HTMLButtonElement>(`[data-tab="${next.id}"]`)
      ?.focus();
  }

  return (
    <section className={`overflow-hidden rounded-lg border border-line bg-surface ${className}`}>
      <div
        ref={strip}
        role="tablist"
        onKeyDown={onKeyDown}
        className="flex gap-1 overflow-x-auto border-b border-line px-2 pt-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {tabs.map((tab) => {
          const selected = tab.id === current.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              data-tab={tab.id}
              id={`${base}-${tab.id}-tab`}
              aria-selected={selected}
              aria-controls={`${base}-${tab.id}-panel`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(tab.id)}
              className={`whitespace-nowrap rounded-t px-3.5 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] transition-colors ${
                selected
                  ? "border-b-2 border-accent text-accent"
                  : "border-b-2 border-transparent text-muted hover:text-ink"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`${base}-${current.id}-panel`}
        aria-labelledby={`${base}-${current.id}-tab`}
        className="p-5 sm:p-6"
      >
        {current.render()}
      </div>
    </section>
  );
}
