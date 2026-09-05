"use client";

import { useEffect, useState } from "react";
import { Pencil } from "lucide-react";
import { useDynamicContext } from "@dynamic-labs/sdk-react-core";
import { AvatarPicker } from "@/components/avatar-picker";
import { Loading } from "@/components/loading";
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
  type?: "text" | "tel";
};

const IDENTITY: Field[] = [
  { key: "full_name", label: "Full name", hint: "The name on your accounts" },
  { key: "phone", label: "Phone", type: "tel", hint: "How a provider would reach you" },
];

// Where this person is reached when a live call stalls and needs them. Per
// user, because everyone using Orion has their own number and inbox.
const ESCALATION: Field[] = [
  {
    key: "escalation_whatsapp",
    label: "WhatsApp number",
    type: "tel",
    hint: "Include the country code, e.g. +2347000000000",
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
 *
 * Read first, edit on request. Details a person has already filled in are
 * something to look at, not a page of input boxes to scroll past - the form
 * only appears once there is a reason for it.
 */
export default function AccountPage() {
  const { user } = useDynamicContext();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [draft, setDraft] = useState<ProfileUpdate>({});
  const [editing, setEditing] = useState(false);
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

  async function save(update: ProfileUpdate) {
    setSaving(true);
    setError(null);
    try {
      // Only what changed - a blank field means "clear this", not "wipe the
      // rest of the profile".
      const updated = await saveProfile({ ...update, email: email ?? undefined });
      setProfile(updated);
      setDraft({});
      setSaved(true);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  const avatar = value("avatar_url");
  const initial = (value("full_name") || email || "?").trim().charAt(0).toUpperCase();

  const language =
    CALL_LANGUAGES.find((l) => l.code === (value("preferred_language") || "en"))?.label ?? "English";

  const summary: [string, string][] = [
    ["Full name", value("full_name")],
    ["Email", email ?? ""],
    ["Phone", value("phone")],
    ["Address", [value("address_line1"), value("address_line2")].filter(Boolean).join(", ")],
    ["City", value("city")],
    ["State or region", value("region")],
    ["Postal code", value("postal_code")],
    ["Country", value("country")],
    ["WhatsApp for alerts", value("escalation_whatsapp")],
    ["Email for alerts", value("escalation_email") || (email ?? "")],
    ["Default call language", language],
  ];

  const missing = summary.filter(([, v]) => !v).length;

  return (
    <div className="max-w-3xl">
      <header className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-line pb-8">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Account</p>
          <h1 className="mt-4 font-display text-[2.0625rem] leading-none text-ink sm:text-[2.4375rem]">
            Your details
          </h1>
          <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
            Fill this in once. Orion uses it on every negotiation.
          </p>
        </div>

        {profile && !editing && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="inline-flex flex-none items-center gap-2 rounded border border-line px-4 py-2 text-[13px] text-ink-soft transition-colors hover:border-accent hover:text-accent"
          >
            <Pencil size={14} />
            Edit
          </button>
        )}
      </header>

      {error && (
        <p className="mt-8 rounded border border-fail/40 bg-fail/5 px-5 py-4 text-[13px] text-fail">
          {error}
        </p>
      )}

      {!profile && !error && <Loading label="Loading your details" />}

      {profile && (
        <>
          <div className="mt-10 flex flex-wrap items-center gap-6">
            {/* Saved on its own the moment a picture is chosen: a photograph is
                not a draft, and nobody expects to press Save after picking one. */}
            <AvatarPicker
              value={avatar}
              initial={initial}
              onChange={(dataUrl) => {
                setDraft((d) => ({ ...d, avatar_url: dataUrl }));
                void save({ avatar_url: dataUrl });
              }}
            />
            <div className="min-w-0">
              <p className="truncate text-[17px] text-ink">{value("full_name") || "Unnamed"}</p>
              <p className="truncate text-[13px] text-muted">
                {email ?? "No email on this session"}
              </p>
              {saved && !editing && <p className="mt-1 text-[12px] text-pass">Saved.</p>}
            </div>
          </div>

          {editing ? (
            <EditForm
              value={value}
              set={set}
              saving={saving}
              onSubmit={(event) => {
                event.preventDefault();
                void save(draft);
              }}
              onCancel={() => {
                setDraft({});
                setEditing(false);
              }}
            />
          ) : (
            <>
              <dl className="mt-10">
                {summary.map(([label, shown]) => (
                  <div
                    key={label}
                    className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-line py-3"
                  >
                    <dt className="text-[13px] text-muted">{label}</dt>
                    <dd
                      className={`min-w-0 break-words text-[14px] sm:text-right ${
                        shown ? "text-ink" : "text-muted/60"
                      }`}
                    >
                      {shown || "Not set"}
                    </dd>
                  </div>
                ))}
              </dl>

              {missing > 0 && (
                <p className="mt-6 text-[13px] leading-relaxed text-ink-soft">
                  {missing} {missing === 1 ? "detail is" : "details are"} still blank. A rep asks
                  for these before discussing an account.
                </p>
              )}
            </>
          )}

          <p className="mt-10 max-w-prose text-[12px] leading-relaxed text-muted">
            Name and address prefill verification. A PIN or SSN is never stored here, only per
            negotiation and encrypted.
          </p>
        </>
      )}
    </div>
  );
}

function EditForm({
  value,
  set,
  saving,
  onSubmit,
  onCancel,
}: {
  value: (key: keyof ProfileUpdate) => string;
  set: (key: keyof ProfileUpdate, next: string) => void;
  saving: boolean;
  onSubmit: (event: React.FormEvent) => void;
  onCancel: () => void;
}) {
  function input(field: Field) {
    return (
      <label key={field.key} className="block">
        <span className="text-[13px] text-ink-soft">{field.label}</span>
        <input
          type={field.type ?? "text"}
          value={value(field.key)}
          onChange={(e) => set(field.key, e.target.value)}
          className="mt-1.5 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
        />
        {field.hint && <span className="mt-1 block text-[12px] text-muted">{field.hint}</span>}
      </label>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-10 space-y-10">
      <section>
        <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">You</p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">{IDENTITY.map(input)}</div>
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

          {ADDRESS.map(input)}
        </div>
      </section>

      <section>
        <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
          If a call needs you
        </p>
        <p className="mt-3 max-w-prose text-[13px] leading-relaxed text-ink-soft">
          Orion messages you mid-call when it needs you. Leave blank and it carries on alone.
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">{ESCALATION.map(input)}</div>
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

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-8">
        <button
          type="submit"
          disabled={saving}
          className="rounded bg-accent px-6 py-2.5 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-line px-5 py-2.5 text-[13px] text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
