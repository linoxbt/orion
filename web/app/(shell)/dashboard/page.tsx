"use client";

import Link from "next/link";
import { Loading } from "@/components/loading";
import { useEffect, useState } from "react";
import {
  isAuthError,
  listNegotiations,
  listRenewals,
  type NegotiationSession,
  type Renewal,
} from "@/lib/api";

function truncate(value: string, head = 8, tail = 4): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

const STATUS: Record<NegotiationSession["status"], { label: string; className: string }> = {
  pending: { label: "Pending", className: "text-muted" },
  calling: { label: "On a call", className: "text-accent" },
  completed: { label: "Completed", className: "text-pass" },
  failed: { label: "Failed", className: "text-fail" },
};

function money(value: number | null): string {
  return value == null ? "-" : `$${value.toFixed(2)}`;
}

export default function DashboardPage() {
  const [items, setItems] = useState<NegotiationSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renewals, setRenewals] = useState<Renewal[]>([]);

  useEffect(() => {
    listRenewals()
      .then(setRenewals)
      .catch(() => setRenewals([]));
  }, []);

  useEffect(() => {
    listNegotiations()
      .then(setItems)
      .catch((err) => {
        // A dead session is the AuthGate's problem, not an error to show.
        if (isAuthError(err)) return;
        setError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  // Seeded examples are shown, so a new account is not an empty page, but they
  // are never counted. A worked example carrying a plausible saving would
  // otherwise be added into this total and read as money actually kept.
  const real = (items ?? []).filter((s) => !s.is_sample);
  const total = real.length;
  const completed = real.filter((s) => s.status === "completed").length;
  // Only verified savings, which is what the label has always claimed. An
  // outcome the call recording does not support is not a saving yet.
  const monthlySavings = real.reduce(
    (sum, s) =>
      s.verified && s.previous_rate != null && s.new_rate != null
        ? sum + (s.previous_rate - s.new_rate)
        : sum,
    0
  );

  const stats = [
    { label: "Negotiations", value: String(total) },
    { label: "Completed", value: String(completed) },
    { label: "Verified monthly saving", value: `$${monthlySavings.toFixed(2)}` },
  ];

  return (
    <div className="max-w-5xl">
      <header className="flex flex-wrap items-end justify-between gap-6 border-b border-line pb-8">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Dashboard</p>
          <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">Your negotiations</h1>
          <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
            Every call Orion has placed on your behalf, and what it recovered.
          </p>
        </div>
        <Link
          href="/negotiate"
          className="rounded bg-accent px-5 py-2.5 text-[13px] font-medium text-accent-ink shadow-sm transition-colors hover:bg-accent-hover"
        >
          New negotiation
        </Link>
      </header>

      {items === null && !error && <Loading label="Loading negotiations" />}

      {error && (
        <div className="mt-10 rounded border border-line bg-surface px-7 py-8">
          <p className="font-display text-[1.4375rem] text-fail">Couldn&rsquo;t load negotiations</p>
          <p className="mt-3 max-w-prose text-[14px] leading-relaxed text-ink-soft">{error}</p>
        </div>
      )}

      {items !== null && !error && (
        <>
          <dl className="mt-10 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3">
            {stats.map((stat) => (
              <div key={stat.label} className="bg-surface px-7 py-6">
                <dt className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                  {stat.label}
                </dt>
                <dd className="tabular mt-3 font-display text-[2.1875rem] leading-none text-ink">
                  {stat.value}
                </dd>
              </div>
            ))}
          </dl>

          {renewals.length > 0 && (
            <section className="mt-10 rounded-lg border border-partial/40 bg-partial/5 px-7 py-6">
              <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                Worth calling again
              </p>
              <h2 className="mt-3 font-display text-[1.5375rem] leading-snug text-ink">
                {renewals.length === 1
                  ? "A promotional rate is about to end"
                  : `${renewals.length} promotional rates are about to end`}
              </h2>
              <p className="mt-3 max-w-prose text-[14px] leading-relaxed text-ink-soft">
              Negotiated rates lapse quietly. Calling before they do is the second win.
            </p>
              <ul className="mt-5 divide-y divide-line border-t border-line">
                {renewals.map((r) => (
                  <li key={r.task_id} className="flex items-center justify-between gap-4 py-3">
                    <div>
                      <p className="text-[14px] text-ink">{r.provider}</p>
                      <p className="text-[12px] text-muted">
                        {r.days_remaining < 0
                          ? `Expired ${Math.abs(r.days_remaining)} days ago`
                          : `${r.days_remaining} days left`}{" "}
                        · ends {r.contract_end_date}
                      </p>
                    </div>
                    <Link
                      href={`/negotiate/${r.task_id}`}
                      className="flex-none text-[13px] text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
                    >
                      Renegotiate
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {items.length === 0 ? (
            <div className="mt-10 rounded-lg border border-line bg-surface px-8 py-16 text-center">
              <p className="font-display text-[1.6875rem] text-ink">Nothing here yet</p>
              <p className="mx-auto mt-4 max-w-sm text-[14px] leading-relaxed text-ink-soft">
                Upload a bill. Orion calls, and only charges if it wins.
              </p>
              <Link
                href="/negotiate"
                className="mt-8 inline-block rounded bg-accent px-6 py-3 text-[14px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
              >
                Start the first one
              </Link>
            </div>
          ) : (
            <div className="mt-10 overflow-x-auto rounded-lg border border-line bg-surface">
              <table className="w-full min-w-[46rem] text-left">
                <thead>
                  <tr className="border-b border-line font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                    <th className="px-6 py-4 font-normal">Provider</th>
                    <th className="px-6 py-4 font-normal">Status</th>
                    <th className="px-6 py-4 text-right font-normal">Was</th>
                    <th className="px-6 py-4 text-right font-normal">Now</th>
                    <th className="px-6 py-4 text-right font-normal">Saved</th>
                    <th className="px-6 py-4 font-normal">Reference</th>
                    <th className="px-6 py-4" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((row) => {
                    const saved =
                      row.previous_rate != null && row.new_rate != null
                        ? row.previous_rate - row.new_rate
                        : null;
                    return (
                      <tr key={row.task_id} className="transition-colors hover:bg-surface-2">
                        <td className="px-6 py-4 text-[14px] text-ink">
                          <span className="inline-flex items-center gap-2">
                            {row.provider}
                            {row.is_sample && (
                              <span
                                title="A worked example, seeded on a new account. Not counted in your totals."
                                className="rounded border border-line px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted"
                              >
                                Example
                              </span>
                            )}
                          </span>
                        </td>
                        <td className={`px-6 py-4 text-[13px] ${STATUS[row.status].className}`}>
                          <span className="inline-flex items-center gap-2">
                            {row.status === "calling" && (
                              <span className="live-dot h-1.5 w-1.5 rounded-full bg-accent" />
                            )}
                            {STATUS[row.status].label}
                          </span>
                        </td>
                        <td className="tabular px-6 py-4 text-right text-[13px] text-ink-soft">
                          {money(row.previous_rate)}
                        </td>
                        <td className="tabular px-6 py-4 text-right text-[13px] text-ink-soft">
                          {money(row.new_rate)}
                        </td>
                        <td
                          className={`tabular px-6 py-4 text-right text-[13px] ${
                            saved && saved > 0 ? "text-pass" : "text-ink-soft"
                          }`}
                        >
                          {saved != null && saved > 0 ? `$${saved.toFixed(2)}/mo` : "-"}
                        </td>
                        <td className="px-6 py-4 font-mono text-[11px] text-muted">
                          {row.confirmation_number ?? truncate(row.task_id)}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Link
                            href={`/negotiate/${row.task_id}`}
                            className="text-[13px] text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
                          >
                            View
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
