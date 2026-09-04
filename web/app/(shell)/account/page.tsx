"use client";

import { useEffect, useState } from "react";
import { useDynamicContext } from "@dynamic-labs/sdk-react-core";
import {
  CALL_LANGUAGES,
  getProfile,
  isAuthError,
  saveProfile,
  type ProfileUpdate,
  type UserProfile,
} from "@/lib/api";

// Kept short and common rather than a full ISO list - a 250-entry dropdown is
// worse than a text field for the handful of countries this actually serves.
const COUNTRIES = [
  "United States",
  "United Kingdom",
  "Canada",
  "Nigeria",
  "Ireland",
  "Australia",
  "Germany",
  "France",
  "Spain",
  "Italy",
  "Netherlands",
  "South Africa",
  "India",
];

type Field = {
  key: keyof ProfileUpdate;
  label: string;
  hint?: string;
  type?: "text" | "tel" | "url";
};

const IDENTITY: Field[] = [
  { key: "full_name", label: "Full name", hint: "The name on your accounts" },
  { key: "phone", label: "Phone", type: "tel", hint: "How a provider would reach you" },
  { key: "avatar_url", label: "Profile picture URL", type: "url" },
];

// Where this person is reached when a live call stalls and needs them. Per
// user, because everyone using Orion has their own number and inbox.
const ESCALATION: Field[] = [
  {
    key: "escalation_whatsapp",
    label: "WhatsApp number",
    type: "tel",
    hint: "Include the country code, e.g. +2349061854649",
  },
  {
    key: "escalation_email",
    label: "Email for alerts",
    hint: "Defaults to your account email if left blank",
  },
];

const ADDRESS: Field[] = [
  { key: "address_line1", label: "Address" },
  { key: "address_line2", label: "Address line 2" },
  { key: "city", label: "City" },
  { key: "region", label: "State or region" },
  { key: "postal_code", label: "Postal code" },
];

/** The customer's own details, kept once.
 *
 * The point isn't a settings page for its own sake: a retention line asks who
 * is calling before it will discuss anything, and these are the answers. Saved
 * here, they prefill every negotiation and seed the verification vault, so
 * nobody types their own address in for the fourth time.
 */
export default function AccountPage() {
  const { user } = useDynamicContext();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [draft, setDraft] = useState<ProfileUpdate>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const email = user?.email ?? profile?.email ?? null;

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setDraft({});
      })
      .catch((err) => {
        if (isAuthError(err)) return;
        setError(
          err instanceof Error && err.message === "supabase_not_configured"
            ? "Profiles aren't connected to the database yet."
            : err instanceof Error
              ? err.message
              : String(err)
        );
      });
  }, []);

  function value(key: keyof ProfileUpdate): string {
    const pending = draft[key];
    if (pending !== undefined) return (pending as string) ?? "";
    const stored = profile?.[key as keyof UserProfile];
    return typeof stored === "string" ? stored : "";
  }

  function set(key: keyof ProfileUpdate, next: string) {
    setSaved(false);
    setDraft((d) => ({ ...d, [key]: next }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // Only what changed - a blank field means "clear this", not "wipe the
      // rest of the profile".
      const updated = await saveProfile({ ...draft, email: email ?? undefined });
      setProfile(updated);
      setDraft({});
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  const avatar = value("avatar_url");
  const initial = (value("full_name") || email || "?").trim().charAt(0).toUpperCase();

  return (
    <div className="max-w-3xl">
      <header className="border-b border-line pb-8">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Account</p>
        <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">Your details</h1>
        <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
        Fill this in once. Orion uses it on every negotiation.
      </p>
      </header>

      <div className="mt-10 flex items-center gap-5">
        {avatar ? (
          // Deliberately a plain img: the URL is user-supplied and arbitrary,
          // which next/image would need every host allow-listed for.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={avatar}
            alt=""
            className="h-16 w-16 flex-none rounded-full border border-line object-cover"
          />
        ) : (
          <span className="flex h-16 w-16 flex-none items-center justify-center rounded-full bg-accent-soft text-[1.4375rem] font-medium text-accent">
            {initial}
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate text-[16px] text-ink">{value("full_name") || "Unnamed"}</p>
          <p className="truncate text-[13px] text-muted">{email ?? "No email on this session"}</p>
        </div>
      </div>

      {error && (
        <p className="mt-8 rounded border border-fail/40 bg-fail/5 px-5 py-4 text-[13px] text-fail">
          {error}
        </p>
      )}

      <form onSubmit={submit} className="mt-10 space-y-10">
        <section>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">You</p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            {IDENTITY.map((field) => (
              <label key={field.key} className="block">
                <span className="text-[13px] text-ink-soft">{field.label}</span>
                <input
                  type={field.type ?? "text"}
                  value={value(field.key)}
                  onChange={(e) => set(field.key, e.target.value)}
                  className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                />
                {field.hint && (
                  <span className="mt-1 block text-[12px] text-muted">{field.hint}</span>
                )}
              </label>
            ))}
          </div>
        </section>

        <section>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">Where you are</p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <label className="block">
              <span className="text-[13px] text-ink-soft">Country</span>
              <input
                list="orion-countries"
                value={value("country")}
                onChange={(e) => set("country", e.target.value)}
                className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
              />
              <datalist id="orion-countries">
                {COUNTRIES.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </label>

            {ADDRESS.map((field) => (
              <label key={field.key} className="block">
                <span className="text-[13px] text-ink-soft">{field.label}</span>
                <input
                  value={value(field.key)}
                  onChange={(e) => set(field.key, e.target.value)}
                  className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                />
              </label>
            ))}
          </div>
        </section>

        <section>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
            If a call needs you
          </p>
          <p className="mt-3 max-w-prose text-[13px] leading-relaxed text-ink-soft">
            Orion messages you mid-call when it needs you. Leave blank and it carries on alone.
          </p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            {ESCALATION.map((field) => (
              <label key={field.key} className="block">
                <span className="text-[13px] text-ink-soft">{field.label}</span>
                <input
                  type={field.type ?? "text"}
                  value={value(field.key)}
                  onChange={(e) => set(field.key, e.target.value)}
                  className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
                />
                {field.hint && (
                  <span className="mt-1 block text-[12px] text-muted">{field.hint}</span>
                )}
              </label>
            ))}
          </div>
        </section>

        <section>
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
            Call preferences
          </p>
          <label className="mt-5 block max-w-sm">
            <span className="text-[13px] text-ink-soft">Default call language</span>
            <select
              value={value("preferred_language") || "en"}
              onChange={(e) => set("preferred_language", e.target.value)}
              className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
            >
              {CALL_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-[12px] text-muted">
              Preselected on every new negotiation. You can still change it per call.
            </span>
          </label>
        </section>

        <div className="flex items-center gap-5 border-t border-line pt-8">
          <button
            type="submit"
            disabled={saving}
            className="rounded bg-accent px-6 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
          {saved && <span className="text-[13px] text-pass">Saved.</span>}
        </div>

        <p className="max-w-prose text-[12px] leading-relaxed text-muted">
        Name and address prefill verification. A PIN or SSN is never stored here, only per
        negotiation and encrypted.
      </p>
      </form>
    </div>
  );
}
