"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { cancelPlan, confirmUpgrade, getPlan, startUpgrade, type PlanState } from "@/lib/api";

/** The plan, what is left of the free allowance, and the way off it.
 *
 * Returning from the payment page proves nothing on its own, so the redirect
 * only prompts this component to ask the server to verify the reference. The
 * account is upgraded by Paystack's signed webhook or by that verification -
 * never by the browser saying it paid.
 */
export function PlanPanel() {
  const [plan, setPlan] = useState<PlanState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setPlan(await getPlan());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Paystack sends the customer back with the reference in the query string.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const reference = params.get("reference") ?? params.get("trxref");
    if (!reference) return;

    setBusy(true);
    confirmUpgrade(reference)
      .then(setPlan)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => {
        setBusy(false);
        // Clear the reference so a refresh does not try to confirm it again.
        window.history.replaceState({}, "", window.location.pathname);
      });
  }, []);

  async function upgrade() {
    setBusy(true);
    setError(null);
    try {
      const { authorization_url } = await startUpgrade();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  if (!plan) {
    return (
      <section className="rounded-lg border border-line bg-surface p-7">
        <p className="text-[14px] text-muted">{error ?? "Loading your plan…"}</p>
      </section>
    );
  }

  const used = plan.limit ? Math.min(plan.used, plan.limit) : 0;
  const pct = plan.limit ? (used / plan.limit) * 100 : 100;
  const exhausted = plan.remaining === 0;

  return (
    <section className="rounded-lg border border-line bg-surface p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">Your plan</p>
          <h2 className="mt-3 font-display text-[1.6875rem] text-ink">
            {plan.unlimited ? "Unlimited" : "Free"}
          </h2>
        </div>
        {plan.unlimited && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-[12px] font-medium text-accent">
            <Check size={13} /> Active
          </span>
        )}
      </div>

      {plan.unlimited ? (
        <>
          <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
            As many bills as you like.{" "}
            {plan.renews && plan.next_payment_at
              ? `Renews ${new Date(plan.next_payment_at).toLocaleDateString()}.`
              : plan.expires_at
                ? `Ends ${new Date(plan.expires_at).toLocaleDateString()}, and will not renew.`
                : ""}
          </p>

          {plan.subscription_status === "attention" && (
            <p className="mt-3 text-[14px] leading-relaxed text-fail">
              The last renewal payment failed. Update your card before the plan lapses.
            </p>
          )}

          {plan.renews && (
            <button
              type="button"
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  setPlan(await cancelPlan());
                } catch (err) {
                  setError(err instanceof Error ? err.message : String(err));
                } finally {
                  setBusy(false);
                }
              }}
              disabled={busy}
              className="mt-5 text-[13px] text-muted underline decoration-transparent underline-offset-4 transition hover:decoration-current disabled:opacity-40"
            >
              Cancel renewal
            </button>
          )}
        </>
      ) : (
        <>
          <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
            {plan.used} of {plan.limit} bills used this month. Resets on the 1st.
          </p>

          <div
            role="progressbar"
            aria-valuenow={used}
            aria-valuemin={0}
            aria-valuemax={plan.limit ?? 0}
            aria-label="Bills used this month"
            className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
          >
            <div
              className={`h-full rounded-full transition-all ${exhausted ? "bg-fail" : "bg-accent"}`}
              style={{ width: `${pct}%` }}
            />
          </div>

          {exhausted && (
            <p className="mt-4 text-[14px] leading-relaxed text-ink">
              You have used this month&rsquo;s bills. Upgrade for unlimited, or wait for the 1st.
            </p>
          )}

          <button
            type="button"
            onClick={upgrade}
            disabled={busy || !plan.can_upgrade}
            className="mt-6 inline-flex items-center gap-2 rounded bg-accent px-5 py-2.5 text-[14px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {busy && <Loader2 size={15} className="animate-spin" />}
            Upgrade for ${plan.price_usd.toFixed(2)} a month
          </button>

          {!plan.can_upgrade && (
            <p className="mt-3 text-[13px] text-muted">
              Payments are not connected on this deployment yet.
            </p>
          )}
        </>
      )}

      {error && <p className="mt-4 text-[14px] text-fail">{error}</p>}
    </section>
  );
}
