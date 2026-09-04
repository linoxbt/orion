"use client";

import { use, useEffect, useState } from "react";
import { FadeIn } from "@/components/fade-in";
import { LiveCallFeed } from "@/components/live-call-feed";
import { AccountDetailsForm } from "@/components/account-details-form";
import { BrowserCall } from "@/components/browser-call";
import { ConsentForm } from "@/components/consent-form";
import { OutboundCall } from "@/components/outbound-call";
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
  calling: "Calling…",
  completed: "Completed",
  failed: "Failed",
};

const STATUS_COLOR: Record<NegotiationSession["status"], string> = {
  pending: "text-muted",
  calling: "text-accent",
  completed: "text-pass",
  failed: "text-fail",
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

  const [hasStripe, setHasStripe] = useState(false);

  useEffect(() => {
    getCapabilities()
      .then((h) => setHasStripe(Boolean(h.capabilities.hasStripe)))
      .catch(() => setHasStripe(false));
  }, []);

  async function handleCharge() {
    setSubmitting(true);
    setActionError(null);
    try {
      const updated = await chargeNegotiation(taskId);
      setSession(updated);
    } catch (err) {
      if (err instanceof ApiError && err.detail === "stripe_not_configured") {
        setActionError("Billing isn't available yet (STRIPE_SECRET_KEY not configured on the backend).");
      } else {
        setActionError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mx-auto max-w-2xl px-6 pb-24">
        <FadeIn>
          <header className="py-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Negotiation</p>
            <h1 className="mt-4 font-display text-[2.4375rem] leading-[1.05] text-ink text-balance">{session?.provider ?? "Loading…"}</h1>
            {session && (
              <p className={`mt-2 font-mono text-sm uppercase tracking-[0.18em] ${STATUS_COLOR[session.status]}`}>
                {STATUS_LABEL[session.status]}
              </p>
            )}
          </header>

          {error && <p className="text-sm text-fail">{error}</p>}

          {session && (
            <section className="rounded border border-line bg-surface p-6">
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <dt className="text-muted">Task ID</dt>
                <dd className="truncate font-mono text-xs">{session.task_id}</dd>
                <dt className="text-muted">Phone number</dt>
                <dd>{session.phone_number}</dd>
                <dt className="text-muted">Authorization</dt>
                <dd>{session.authorized ? "Authorised" : "Not yet authorised"}</dd>
                <dt className="text-muted">Call SID</dt>
                <dd className="truncate font-mono text-xs">{session.call_sid ?? "-"}</dd>
                <dt className="text-muted">Outcome</dt>
                <dd>{session.outcome ?? "-"}</dd>
                <dt className="text-muted">Previous rate</dt>
                <dd>{session.previous_rate != null ? `$${session.previous_rate}/mo` : "-"}</dd>
                <dt className="text-muted">New rate</dt>
                <dd>{session.new_rate != null ? `$${session.new_rate}/mo` : "-"}</dd>
                <dt className="text-muted">Confirmation #</dt>
                <dd>{session.confirmation_number ?? "-"}</dd>
                <dt className="text-muted">Success fee charged</dt>
                <dd>{session.fee_amount_cents != null ? `$${(session.fee_amount_cents / 100).toFixed(2)}` : "-"}</dd>
              </dl>
            </section>
          )}

          {session && <LiveCallFeed taskId={taskId} />}

          {session && !session.verified && <AccountDetailsForm taskId={taskId} />}

          {session && !session.verified && (
            <BrowserCall taskId={taskId} contact={session.provider} />
          )}

          {session && !session.authorized && (
            <ConsentForm taskId={taskId} onConsented={setSession} />
          )}

          {session && <OutboundCall session={session} onPlaced={setSession} />}

          {session && !session.verified && (
            <form onSubmit={handleComplete} className="mt-6 rounded border border-line bg-surface p-6">
              <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                Record the outcome yourself
              </p>
              <label className="block text-sm">
                <span className="text-muted">Outcome</span>
                <input
                  required
                  value={outcome}
                  onChange={(e) => setOutcome(e.target.value)}
                  placeholder="e.g. reduced rate"
                  className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                />
              </label>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="text-muted">Previous rate ($/mo)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={previousRate}
                    onChange={(e) => setPreviousRate(e.target.value)}
                    className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                  />
                </label>
                <label className="block text-sm">
                  <span className="text-muted">New rate ($/mo)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={newRate}
                    onChange={(e) => setNewRate(e.target.value)}
                    className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                  />
                </label>
              </div>
              <label className="mt-4 block text-sm">
                <span className="text-muted">Confirmation number</span>
                <input
                  value={confirmationNumber}
                  onChange={(e) => setConfirmationNumber(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                />
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="mt-6 w-full rounded bg-accent px-4 py-2.5 text-[13px] font-medium text-accent-ink hover:bg-accent-hover disabled:opacity-40"
              >
                {submitting ? "Saving…" : "Mark verified"}
              </button>
            </form>
          )}

          {/* Only where a card processor is actually connected. This offered a
              "Charge success fee" button on every verified negotiation, which
              on a deployment without Stripe - and Stripe does not serve
              Nigerian merchants - could only ever answer 503. */}
          {hasStripe && session?.verified && !session.stripe_payment_intent_id && (
            <div className="mt-6 rounded border border-line bg-surface p-6">
              <button
                type="button"
                onClick={handleCharge}
                disabled={submitting}
                className="w-full rounded bg-accent px-4 py-2.5 text-[13px] font-medium text-accent-ink hover:bg-accent-hover disabled:opacity-40"
              >
                {submitting ? "Charging…" : "Charge success fee"}
              </button>
            </div>
          )}

          {actionError && <p className="mt-3 text-sm text-partial">{actionError}</p>}
        </FadeIn>
      </div>
    </div>
  );
}
