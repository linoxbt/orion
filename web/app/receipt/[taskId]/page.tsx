"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Loading } from "@/components/loading";
import { Wordmark } from "@/components/wordmark";
import { getReceipt, type Receipt } from "@/lib/api";

/** Public proof of a saving.
 *
 * Deliberately outside the signed-in shell and deliberately thin: provider,
 * before, after, confirmation number. No phone number, no account details, no
 * transcript. A link someone forwards to a friend must not become a way to
 * read a stranger's account - and the backend refuses to serve a receipt for a
 * negotiation that was never verified, because there would be nothing to prove.
 */
export default function ReceiptPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = use(params);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReceipt(taskId)
      .then(setReceipt)
      .catch(() => setError("No verified saving to show for this negotiation."));
  }, [taskId]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
          <Link href="/" className="transition-opacity hover:opacity-70">
            <Wordmark className="text-[1.2875rem]" />
          </Link>
          <Link
            href="/negotiate"
            className="text-[13px] text-accent underline decoration-transparent underline-offset-4 transition hover:decoration-current"
          >
            Negotiate yours
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-20">
        {error && <p className="text-[14px] leading-relaxed text-ink-soft">{error}</p>}

        {!receipt && !error && <Loading label="Opening receipt" />}

        {receipt && (
          <>
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
              {receipt.is_sample ? "Example receipt" : "Verified saving"}
            </p>
            {receipt.is_sample && (
              <p className="mt-4 rounded border border-line bg-surface-2 p-4 text-[13px] leading-relaxed text-ink-soft">
                This is a worked example, seeded on a new account to show what a receipt looks
                like. Nobody was called and no money was saved.
              </p>
            )}
            <h1 className="mt-5 font-display text-display-md leading-[1.05] text-ink">
              {receipt.monthly_saving != null
                ? `$${receipt.monthly_saving.toFixed(2)} a month off ${receipt.provider}.`
                : `${receipt.provider} - settled.`}
            </h1>

            {receipt.annual_saving != null && (
              <p className="mt-6 text-[16px] leading-relaxed text-ink-soft">
                That&rsquo;s{" "}
                <span className="tabular text-ink">${receipt.annual_saving.toFixed(2)}</span> over a
                year, for a call nobody had to sit through.
              </p>
            )}

            <dl className="mt-14 grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-3">
              <div className="bg-surface px-7 py-6">
                <dt className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                  Was paying
                </dt>
                <dd className="tabular mt-3 font-display text-[1.9375rem] leading-none text-ink">
                  {receipt.previous_rate != null ? `$${receipt.previous_rate.toFixed(2)}` : "-"}
                </dd>
              </div>
              <div className="bg-surface px-7 py-6">
                <dt className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                  Now pays
                </dt>
                <dd className="tabular mt-3 font-display text-[1.9375rem] leading-none text-pass">
                  {receipt.new_rate != null ? `$${receipt.new_rate.toFixed(2)}` : "-"}
                </dd>
              </div>
              <div className="bg-surface px-7 py-6">
                <dt className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                  Reference
                </dt>
                <dd className="mt-3 font-mono text-[14px] text-ink">
                  {receipt.confirmation_number ?? "-"}
                </dd>
              </div>
            </dl>

            {receipt.outcome && (
              <p className="mt-10 max-w-prose text-[15px] leading-[1.7] text-ink-soft">
                {receipt.outcome}
              </p>
            )}

            <p className="mt-12 border-t border-line pt-6 text-[12px] leading-relaxed text-muted">
              Anyone with this link can see this page - it deliberately carries no account number,
              phone number or transcript.{" "}
              {receipt.verification_source === "assemblyai"
                ? "Confirmed from a transcript of the recorded call, not self-reported."
                : "Outcome confirmed by a human reviewer."}{" "}
              Orion identifies itself as an AI representative on every call it makes.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
