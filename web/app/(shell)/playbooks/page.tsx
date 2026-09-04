"use client";

import { useEffect, useState } from "react";
import { listPlaybooks, type Playbook } from "@/lib/api";

const VERTICAL_ORDER = ["cable_internet", "cell_phone", "medical"];

function groupByVertical(playbooks: Playbook[]) {
  const generic = new Map<string, Playbook>();
  const specific = new Map<string, Playbook[]>();

  for (const playbook of playbooks) {
    if (playbook.provider) {
      const list = specific.get(playbook.vertical) ?? [];
      list.push(playbook);
      specific.set(playbook.vertical, list);
    } else {
      generic.set(playbook.vertical, playbook);
    }
  }

  return VERTICAL_ORDER.filter((vertical) => generic.has(vertical)).map((vertical) => ({
    vertical,
    generic: generic.get(vertical)!,
    providers: specific.get(vertical) ?? [],
  }));
}

function ProviderCard({ playbook }: { playbook: Playbook }) {
  return (
    <div className="rounded border border-line bg-surface2 p-5">
      <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
        {playbook.provider}
      </p>
      <h3 className="font-display text-[1.1875rem]">{playbook.display_name}</h3>
      <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{playbook.strategy_notes}</p>

      {playbook.retention_routing && (
        <p className="mt-3 text-xs leading-relaxed text-ink/70">
          <span className="font-mono uppercase tracking-[0.22em] text-muted">Routing - </span>
          {playbook.retention_routing}
        </p>
      )}

      {playbook.trigger_phrases.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {playbook.trigger_phrases.map((phrase) => (
            <span
              key={phrase}
              className="rounded border border-line bg-surface px-2 py-1 text-[10px] leading-snug text-ink/70"
            >
              &ldquo;{phrase}&rdquo;
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listPlaybooks()
      .then(setPlaybooks)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  return (
    <div className="max-w-3xl">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Playbooks</p>
      <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">Negotiation strategy by vertical</h1>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
      Public retention tactics as a baseline, with a provider-specific playbook where one
      exists. Which desk to ask for and what tends to work, not proprietary offer tiers.
    </p>

      {error && (
        <div className="mt-8 rounded border border-fail/40 bg-fail/10 px-6 py-6 text-center">
          <p className="text-sm text-fail">{error}</p>
        </div>
      )}

      {playbooks === null && !error && (
        <div className="mt-8 rounded border border-line bg-surface px-6 py-10 text-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Loading…</p>
        </div>
      )}

      {playbooks !== null && (
        <div className="mt-8 flex flex-col gap-10">
          {groupByVertical(playbooks).map(({ vertical, generic, providers }) => (
            <section key={vertical}>
              <div className="rounded border border-line bg-surface p-6">
                <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                  {generic.vertical}
                </p>
                <h2 className="font-display text-[1.3875rem]">{generic.display_name}</h2>
                <p className="mt-2 text-[14px] leading-relaxed text-ink-soft">{generic.strategy_notes}</p>
              </div>

              {providers.length > 0 && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {providers.map((playbook) => (
                    <ProviderCard key={`${playbook.vertical}-${playbook.provider}`} playbook={playbook} />
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
