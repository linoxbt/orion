"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { FadeIn } from "@/components/fade-in";
import { Loading } from "@/components/loading";
import { LiveCallFeed } from "@/components/live-call-feed";
import { AccountDetailsForm } from "@/components/account-details-form";
import { BrowserCall } from "@/components/browser-call";
import { ConsentForm } from "@/components/consent-form";
import { OutboundCall } from "@/components/outbound-call";
import { CallHistory } from "@/components/call-history";
import { Tabs } from "@/components/tabs";
import {
  ApiError,
  chargeNegotiation,
  getCapabilities,
  completeNegotiation,
  getNegotiation,
  type NegotiationSession,
} from "@/lib/api";

const STATUS_LABEL: Record<NegotiationSession["status"], string> = {
  pending: "Pending",
  calling: "On a call",
  completed: "Completed",
  failed: "Failed",
};

/** Border, text and wash for the status pill, in that order. */
const STATUS_TONE: Record<NegotiationSession["status"], string> = {
  pending: "border-line text-muted",
  calling: "border-accent/50 text-accent bg-accent-soft",
  completed: "border-pass/40 text-pass",
  failed: "border-fail/40 text-fail",
};

export default function NegotiationStatusPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = use(params);

  const [session, setSession] = useState<NegotiationSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [outcome, setOutcome] = useState("");
  const [previousRate, setPreviousRate] = useState("");
  const [newRate, setNewRate] = useState("");
  const [confirmationNumber, setConfirmationNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hasStripe, setHasStripe] = useState(false);

  useEffect(() => {
    let cancelled = false;

    function poll() {
      getNegotiation(taskId)
        .then((s) => {
          if (!cancelled) setSession(s);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : String(err));
        });
    }

    poll();
    const interval = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [taskId]);

  useEffect(() => {
    getCapabilities()
      .then((h) => setHasStripe(Boolean(h.capabilities.hasStripe)))
      .catch(() => setHasStripe(false));
  }, []);

  async function handleComplete(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setActionError(null);
    try {
      const updated = await completeNegotiation(taskId, {
        outcome,
        previous_rate: previousRate ? Number(previousRate) : undefined,
        new_rate: newRate ? Number(newRate) : undefined,
        confirmation_number: confirmationNumber || undefined,
      });
      setSession(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCharge() {
    setSubmitting(true);
    setActionError(null);
    try {
      const updated = await chargeNegotiation(taskId);
      setSession(updated);
    } catch (err) {
      if (err instanceof ApiError && err.detail === "stripe_not_configured") {
        setActionError("Billing isn't connected on the backend yet.");
      } else {
        setActionError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-6xl py-24">
        {error ? <p className="text-[14px] text-fail">{error}</p> : <Loading label="Opening negotiation" />}
      </div>
    );
  }

  const saving =
    session.previous_rate != null && session.new_rate != null
      ? session.previous_rate - session.new_rate
      : null;

  return (
    <div className="mx-auto max-w-6xl pb-24">
      <FadeIn onMount>
        {/* Header: what this is, and where it stands, on one line. */}
        <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4 py-8 sm:py-10">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
              <Link href="/dashboard" className="transition-colors hover:text-ink">
                Negotiations
              </Link>
              <span className="px-2 text-line">/</span>
              {session.vertical.replace(/_/g, " ")}
            </p>
            <h1 className="mt-3 truncate font-display text-[1.75rem] leading-[1.05] text-ink sm:text-[2.0625rem]">
              {session.provider}
            </h1>
            <p className="tabular mt-2 font-mono text-[11px] text-muted">
              {session.phone_number}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${STATUS_TONE[session.status]}`}
            >
              {STATUS_LABEL[session.status]}
            </span>
            <span
              className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${
                session.verified ? "border-pass/40 text-pass" : "border-line text-muted"
              }`}
            >
              {session.verified ? "Verified" : "Unverified"}
            </span>
            <span
              className={`rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${
                session.authorized ? "border-line text-ink-soft" : "border-partial/50 text-partial"
              }`}
            >
              {session.authorized ? "Authorised" : "Not authorised"}
            </span>
          </div>
        </header>

        {error && <p className="mb-6 text-[13px] text-fail">{error}</p>}

        {/* The four numbers this page exists to report. */}
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
          <Kpi
            label="Monthly saving"
            value={saving != null ? money(saving) : "—"}
            tone={saving != null && saving > 0 ? "good" : undefined}
            note={session.verified ? "verified from the recording" : "not verified yet"}
          />
          <Kpi label="Was" value={money(session.previous_rate)} note="per month" />
          <Kpi label="Now" value={money(session.new_rate)} note="per month" />
          <Kpi
            label="A year"
            value={saving != null ? money(saving * 12) : "—"}
            note="if the rate holds"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.85fr)_minmax(0,1fr)] lg:items-start">
          {/* Left: what is happening, and what happened. */}
          <div className="min-w-0 space-y-6">
            {session.recommendation && (
              <section className="rounded-lg border border-accent/40 bg-accent-soft p-5 sm:p-7">
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent">
                  What Orion makes of it
                </p>
                <p className="mt-4 text-[15px] leading-relaxed text-ink">{session.recommendation}</p>
                {session.outcome && (
                  <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{session.outcome}</p>
                )}
              </section>
            )}

            {!session.authorized && <ConsentForm taskId={taskId} onConsented={setSession} />}

            <OutboundCall session={session} onPlaced={setSession} />

            <LiveCallFeed taskId={taskId} />

            {session.status !== "pending" && !session.is_sample && (
              <Panel eyebrow="Call history" title="Every call made">
                <CallHistory taskId={taskId} />
              </Panel>
            )}

            {!session.verified && <BrowserCall taskId={taskId} contact={session.provider} />}
          </div>

          {/* Right: the record, and the things done to it. Tabbed, because the
              verification answers and a hand-typed outcome are things you fill
              in once and then never look at, and both open at once buried the
              record itself. Sticky on a wide screen so the figures stay beside
              whichever call is being read. */}
          <div className="min-w-0 space-y-6 lg:sticky lg:top-6">
            <Tabs
              tabs={[
                {
                  id: "record",
                  label: "Record",
                  render: () => (
                    <Rows
                      rows={[
                        ["Provider", session.provider],
                        ["Number called", session.phone_number],
                        ["Account type", session.vertical.replace(/_/g, " ")],
                        ["Outcome", session.outcome ?? "—"],
                        ["Confirmation #", session.confirmation_number ?? "—"],
                        [
                          "Previous rate",
                          session.previous_rate != null ? `${money(session.previous_rate)}/mo` : "—",
                        ],
                        ["New rate", session.new_rate != null ? `${money(session.new_rate)}/mo` : "—"],
                        [
                          "Success fee",
                          session.fee_amount_cents != null
                            ? money(session.fee_amount_cents / 100)
                            : "not charged",
                        ],
                        ["Reference", session.task_id],
                      ]}
                    />
                  ),
                },
                // Both of these are only worth showing while the outcome is
                // still open. Once it is verified there is nothing to verify
                // with and nothing left to record.
                ...(session.verified
                  ? []
                  : [
                      {
                        id: "verification",
                        label: "Verification",
                        render: () => <AccountDetailsForm taskId={taskId} />,
                      },
                      {
                        id: "outcome",
                        label: "Outcome",
                        render: () => (
                          <>
                            <p className="text-[13px] leading-relaxed text-ink-soft">
                              Orion writes this from the recording. Fill it in only where a call
                              happened outside Orion.
                            </p>
                            <form onSubmit={handleComplete} className="mt-5 space-y-4">
                              <Field
                                label="Outcome"
                                value={outcome}
                                onChange={setOutcome}
                                required
                                placeholder="e.g. reduced rate"
                              />
                              <div className="grid grid-cols-2 gap-3">
                                <Field
                                  label="Was ($/mo)"
                                  value={previousRate}
                                  onChange={setPreviousRate}
                                  type="number"
                                />
                                <Field
                                  label="Now ($/mo)"
                                  value={newRate}
                                  onChange={setNewRate}
                                  type="number"
                                />
                              </div>
                              <Field
                                label="Confirmation number"
                                value={confirmationNumber}
                                onChange={setConfirmationNumber}
                              />
                              <button
                                type="submit"
                                disabled={submitting}
                                className="w-full rounded bg-accent px-4 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
                              >
                                {submitting ? "Saving…" : "Mark verified"}
                              </button>
                            </form>
                          </>
                        ),
                      },
                    ]),
              ]}
            />

            {/* Only where a card processor is actually connected: without one
                this button could never answer anything but a 503. */}
            {hasStripe && session.verified && !session.stripe_payment_intent_id && (
              <Panel eyebrow="Billing" title="Success fee">
                <button
                  type="button"
                  onClick={handleCharge}
                  disabled={submitting}
                  className="mt-4 w-full rounded bg-accent px-4 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
                >
                  {submitting ? "Charging…" : "Charge success fee"}
                </button>
              </Panel>
            )}

            {actionError && <p className="text-[13px] text-partial">{actionError}</p>}
          </div>
        </div>
      </FadeIn>
    </div>
  );
}

function money(value: number | null | undefined): string {
  return value == null ? "—" : `$${value.toFixed(2)}`;
}

/** The page's one card shape, so every block on it lines up. */
function Panel({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-line bg-surface p-5 sm:p-7">
      <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">{eyebrow}</p>
      <h2 className="mt-3 font-display text-[1.375rem] leading-snug text-ink">{title}</h2>
      {children}
    </section>
  );
}

/** Label on the left, value on the right, one per line - a record reads as a
 * list, not as a paragraph. */
function Rows({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="mt-5">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="flex items-baseline justify-between gap-6 border-b border-line py-2.5 last:border-b-0"
        >
          <dt className="flex-none text-[13px] text-muted">{label}</dt>
          <dd className="tabular min-w-0 truncate text-right text-[13px] text-ink" title={value}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="text-muted">{label}</span>
      <input
        type={type}
        step={type === "number" ? "0.01" : undefined}
        required={required}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
      />
    </label>
  );
}

/** One figure in the header strip. Big-number tiles are spent only here, on
 * the four numbers the page exists to report. */
function Kpi({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "good";
}) {
  return (
    <div className="min-w-0 bg-surface p-4 sm:p-5">
      <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted">{label}</p>
      <p
        className={`tabular mt-3 text-[1.375rem] font-medium leading-none tracking-tight sm:text-[1.625rem] ${
          tone === "good" ? "text-pass" : "text-ink"
        }`}
      >
        {value}
      </p>
      {note && <p className="mt-2 text-[12px] leading-snug text-muted">{note}</p>}
    </div>
  );
}
