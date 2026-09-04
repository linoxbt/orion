"use client";

import { useState } from "react";
import { recordConsent, type NegotiationSession } from "@/lib/api";

const CONSENT_TEXT =
  "I authorise Orion to contact this company as my representative regarding this account " +
  "or purchase, to discuss it on my behalf, and to record the call for verification. " +
  "I confirm I am the account holder or am otherwise entitled to authorise this.";

/** Authorisation to act as the customer's representative.
 *
 * Consent genuinely is required before calling a company about someone's
 * account. Requiring DocuSign for it was not: with DocuSign unconfigured,
 * `authorized` could never become true, so the call button never rendered and
 * no call could ever be placed. This records the same undertaking - the name
 * typed, the wording's version and the moment of agreement - and DocuSign
 * stays available for anyone who wants a countersigned envelope.
 */
export function ConsentForm({
  taskId,
  onConsented,
}: {
  taskId: string;
  onConsented: (session: NegotiationSession) => void;
}) {
  const [name, setName] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      onConsented(await recordConsent(taskId, { signer_name: name.trim(), agreed }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-6 sm:p-7">
      <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
        Authorisation
      </p>
      <h2 className="mt-3 font-display text-[1.5375rem] leading-snug text-ink">
        Authorise Orion to make this call
      </h2>

      <p className="mt-5 rounded border border-line bg-surface-2 px-5 py-4 text-[14px] leading-[1.7] text-ink-soft">
        {CONSENT_TEXT}
      </p>

      <form onSubmit={submit} className="mt-6">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-1 h-4 w-4 flex-none accent-[color:var(--accent)]"
          />
          <span className="text-[14px] leading-relaxed text-ink">I agree to the above.</span>
        </label>

        <label className="mt-5 block">
          <span className="text-[13px] text-ink-soft">Type your full name to sign</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
          />
        </label>

        <button
          type="submit"
          disabled={saving || !agreed || !name.trim()}
          className="mt-6 rounded bg-accent px-5 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {saving ? "Recording…" : "Authorise"}
        </button>
        {error && <p className="mt-3 text-[13px] text-fail">{error}</p>}

        <p className="mt-5 max-w-prose text-[12px] leading-relaxed text-muted">
          Your name, the exact wording you agreed to, and the time are recorded against this
          negotiation. Orion identifies itself as an AI representative on every call and gives a
          recording notice.
        </p>
      </form>
    </section>
  );
}
