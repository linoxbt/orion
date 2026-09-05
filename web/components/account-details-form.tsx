"use client";

import { useEffect, useState } from "react";
import { listAccountDetails, saveAccountDetails, type AccountDetails } from "@/lib/api";

// What a retention line actually asks before it will discuss an account. Not
// all of it, every time - supply what your provider asks for.
const FIELDS: { key: keyof AccountDetails; label: string; hint?: string; sensitive?: boolean }[] = [
  { key: "account_holder_name", label: "Name on the account" },
  { key: "account_number", label: "Account number", hint: "From the bill" },
  { key: "service_address", label: "Service address" },
  { key: "billing_zip", label: "Billing ZIP" },
  { key: "security_pin", label: "Account PIN or passcode", sensitive: true },
  { key: "last4_ssn", label: "Last 4 of SSN", hint: "Only if your provider asks", sensitive: true },
  { key: "date_of_birth", label: "Date of birth", hint: "Common on medical accounts" },
];

/** Collects the details Orion needs to get past "can I verify the account?".
 *
 * Without them a real call ends at that question - it is the single most
 * common reason a third party gets nowhere on a provider line.
 */
export function AccountDetailsForm({ taskId }: { taskId: string }) {
  const [values, setValues] = useState<AccountDetails>({});
  const [onFile, setOnFile] = useState<string[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAccountDetails(taskId)
      .then((res) => setOnFile(res.fields))
      .catch(() => setOnFile([]));
  }, [taskId]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const supplied = Object.fromEntries(
        Object.entries(values).filter(([, value]) => value && value.trim())
      );
      if (Object.keys(supplied).length === 0) {
        setError("Fill in at least one field.");
        return;
      }
      await saveAccountDetails(taskId, supplied);
      const refreshed = await listAccountDetails(taskId);
      setOnFile(refreshed.fields);
      // Cleared from the browser as soon as they're stored.
      setValues({});
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(
        detail === "account_vault_not_configured"
          ? "The server can't store these securely yet (ACCOUNT_ENCRYPTION_KEY is unset)."
          : detail
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    // No card of its own: this lives inside a tab on the negotiation page, and
    // the tab strip is already the heading.
    <div>
      <p className="text-[13px] leading-relaxed text-ink-soft">
        The answers a rep will ask for. Without them the call ends at verification.
      </p>

      {onFile !== null && onFile.length > 0 && (
        <p className="mt-4 rounded border border-line bg-surface-2 px-4 py-3 text-[13px] text-ink-soft">
          On file:{" "}
          <span className="text-ink">
            {onFile.map((f) => f.replace(/_/g, " ")).join(", ")}
          </span>
          . Values are encrypted and can&rsquo;t be read back - re-enter a field to replace it.
        </p>
      )}

      <form onSubmit={handleSave} className="mt-5 grid gap-4">
        {FIELDS.map((field) => (
          <label key={field.key} className="block">
            <span className="text-[13px] text-ink-soft">{field.label}</span>
            <input
              type={field.sensitive ? "password" : "text"}
              autoComplete="off"
              value={values[field.key] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
              className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
            />
            {field.hint && <span className="mt-1 block text-[12px] text-muted">{field.hint}</span>}
          </label>
        ))}

        <div>
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-accent px-5 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save securely"}
          </button>
          {error && <p className="mt-3 text-[13px] text-fail">{error}</p>}
          <p className="mt-4 max-w-prose text-[12px] leading-relaxed text-muted">
          Encrypted at rest, never read back, released one field at a time and logged on the
          timeline.
        </p>
        </div>
      </form>
    </div>
  );
}
