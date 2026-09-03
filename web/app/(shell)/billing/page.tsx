"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listNegotiations, type NegotiationSession } from "@/lib/api";

function truncate(value: string, head = 8, tail = 4): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export default function BillingPage() {
  const [items, setItems] = useState<NegotiationSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listNegotiations()
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const charged = (items ?? []).filter((s) => s.stripe_payment_intent_id != null);
  const awaitingCharge = (items ?? []).filter((s) => s.verified && s.stripe_payment_intent_id == null);
  const totalChargedCents = charged.reduce((sum, s) => sum + (s.fee_amount_cents ?? 0), 0);

  return (
    <div className="max-w-4xl">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Billing</p>
      <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">Success fees</h1>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
        A percentage of verified savings, charged via Stripe once a negotiation is marked verified - never charged before an outcome is confirmed.
      </p>

      {error && (
        <div className="mt-8 rounded border border-fail/40 bg-fail/10 px-6 py-6 text-center">
          <p className="text-sm text-fail">{error}</p>
        </div>
      )}

      {items === null && !error && (
        <div className="mt-8 rounded border border-line bg-surface px-6 py-10 text-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Loading…</p>
        </div>
      )}

      {items !== null && (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <div className="rounded border border-line bg-surface p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">Charged</p>
              <p className="mt-1 font-display text-[1.8375rem]">{charged.length}</p>
            </div>
            <div className="rounded border border-line bg-surface p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">Awaiting charge</p>
              <p className="mt-1 font-display text-[1.8375rem]">{awaitingCharge.length}</p>
            </div>
            <div className="rounded border border-line bg-surface p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">Total collected</p>
              <p className="mt-1 font-display text-[1.8375rem]">${(totalChargedCents / 100).toFixed(2)}</p>
            </div>
          </div>

          {awaitingCharge.length > 0 && (
            <div className="mt-8 rounded border border-partial/40 bg-partial/10 px-4 py-3 text-sm">
              <span className="font-mono text-partial">
                {awaitingCharge.length} negotiation{awaitingCharge.length === 1 ? "" : "s"} verified but not yet charged
              </span>{" "} - open one from the list below to charge it.
            </div>
          )}

          {charged.length === 0 && awaitingCharge.length === 0 && (
            <div className="mt-8 rounded border border-line bg-surface px-6 py-10 text-center">
              <p className="font-display text-[1.3875rem]">Nothing charged yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink/70">
                Charges show up here once a negotiation is verified and the success fee is captured.
              </p>
            </div>
          )}

          {(charged.length > 0 || awaitingCharge.length > 0) && (
            <div className="mt-8 overflow-x-auto rounded border border-line">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead>
                  <tr className="border-b border-line bg-surface font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Monthly savings</th>
                    <th className="px-4 py-3">Fee</th>
                    <th className="px-4 py-3">Payment intent</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {[...charged, ...awaitingCharge].map((row) => {
                    const savings =
                      row.previous_rate != null && row.new_rate != null ? row.previous_rate - row.new_rate : null;
                    return (
                      <tr key={row.task_id} className="hover:bg-surface/60">
                        <td className="px-4 py-3 text-xs">{row.provider}</td>
                        <td className="px-4 py-3 text-xs">{savings != null ? `$${savings.toFixed(2)}/mo` : "-"}</td>
                        <td className="px-4 py-3 text-xs">
                          {row.fee_amount_cents != null ? `$${(row.fee_amount_cents / 100).toFixed(2)}` : "not yet charged"}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-muted">
                          {row.stripe_payment_intent_id ? truncate(row.stripe_payment_intent_id) : "-"}
                        </td>
                        <td className="px-4 py-3 text-xs">
                          <Link href={`/negotiate/${row.task_id}`} className="text-accent hover:underline">
                            View →
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
