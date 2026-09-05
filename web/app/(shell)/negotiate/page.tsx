"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FadeIn } from "@/components/fade-in";
import {
  ApiError,
  CALL_LANGUAGES,
  getProfile,
  ingestBill,
  listPlaybooks,
  startNegotiation,
  type BillExtraction,
  type Playbook,
} from "@/lib/api";

export default function NegotiatePage() {
  const router = useRouter();

  const [playbooks, setPlaybooks] = useState<Playbook[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  // Running out of the monthly allowance is not a failure to explain away -
  // it has a specific remedy, so it gets its own state and its own link.
  const [limitReached, setLimitReached] = useState(false);
  const [extraction, setExtraction] = useState<BillExtraction | null>(null);

  const [provider, setProvider] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [vertical, setVertical] = useState("cable_internet");
  const [language, setLanguage] = useState("en");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    listPlaybooks()
      .then(setPlaybooks)
      .catch(() => setPlaybooks([]));
  }, []);

  useEffect(() => {
    // The form always sent a language, so the backend's fallback to the
    // account preference could never fire - the setting on the account page
    // was inert. Seed the picker from it instead.
    getProfile()
      .then((p) => {
        if (p.preferred_language) setLanguage(p.preferred_language);
      })
      .catch(() => {
        // No profile yet, or profiles aren't connected - English stands.
      });
  }, []);

  async function handleExtract() {
    if (!file) return;
    setExtracting(true);
    setExtractError(null);
    setLimitReached(false);
    try {
      const result = await ingestBill(file);
      setExtraction(result);
      setProvider(result.provider);
      // The bill often prints the number to call, which saves the customer
      // hunting for a retention line.
      if (result.support_phone) setPhoneNumber(result.support_phone);
      // The document usually says what kind of account this is, so don't make
      // someone classify their own bill.
      const guessed =
        result.document_type === "medical_bill"
          ? "medical"
          : /mobile|wireless|cell|phone/i.test(result.plan_details ?? result.merchant_type ?? "")
            ? "cell_phone"
            : result.is_negotiable
              ? "cable_internet"
              : null;
      if (guessed) setVertical(guessed);
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "";
      if (detail.startsWith("free_limit_reached")) {
        setLimitReached(true);
      } else if (detail === "gemini_not_configured") {
        setExtractError(
          "Bill extraction isn't configured on the server yet. Enter the provider name manually below."
        );
      } else if (detail.startsWith("extraction_busy")) {
        setExtractError("The extraction model is busy right now. Try again in a few seconds.");
      } else if (detail.startsWith("unreadable_document")) {
        setExtractError(
          "That file couldn't be read as a bill. A clearer photo or the original PDF usually works."
        );
      } else if (detail.startsWith("unsupported_file_type")) {
        setExtractError("Upload a PDF or a photo of the bill.");
      } else if (detail.startsWith("file_too_large")) {
        setExtractError("That file is over 20MB. Try a smaller photo or the original PDF.");
      } else {
        setExtractError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setExtracting(false);
    }
  }

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    setStarting(true);
    setStartError(null);
    try {
      const session = await startNegotiation({
        provider,
        phone_number: phoneNumber,
        vertical,
        language,
        // Without this the agent walks into the call knowing only a name.
        bill: extraction,
      });
      router.push(`/negotiate/${session.task_id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div>
      <div className="mx-auto max-w-2xl pb-24">
        <FadeIn onMount>
          <header className="py-8 sm:py-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">New negotiation</p>
            <h1 className="mt-4 font-display text-[1.875rem] leading-[1.05] text-ink text-balance sm:text-[2.4375rem]">Let Orion make the call.</h1>
            <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
              Upload a bill, confirm the details, authorise the call.
            </p>
          </header>

          <section className="rounded-lg border border-line bg-surface p-5 sm:p-7">
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">1. Upload your bill</p>
            <input
              type="file"
              accept="image/*,application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-ink-soft file:mr-4 file:rounded file:border file:border-line file:bg-surface file:px-3 file:py-1.5 file:text-sm file:text-ink-soft"
            />
            <button
              type="button"
              onClick={handleExtract}
              disabled={!file || extracting}
              className="mt-4 rounded bg-accent px-4 py-2 text-[13px] font-medium text-accent-ink hover:bg-accent-hover disabled:opacity-40"
            >
              {extracting ? "Extracting…" : "Extract bill details"}
            </button>
            {limitReached && (
              <div className="mt-4 rounded border border-line bg-surface-2 p-5">
                <p className="text-[14px] leading-relaxed text-ink">
                  You have used this month&rsquo;s five bills on the free plan.
                </p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
                  The allowance comes back on the 1st, or upgrade for unlimited bills.
                </p>
                <Link
                  href="/billing"
                  className="mt-4 inline-flex rounded bg-accent px-4 py-2 text-[13px] font-medium text-accent-ink transition-colors hover:bg-accent-hover"
                >
                  See plans
                </Link>
              </div>
            )}
            {extractError && <p className="mt-3 text-sm text-partial">{extractError}</p>}
            {extraction && <ExtractionSummary extraction={extraction} />}
          </section>

          <form onSubmit={handleStart} className="mt-6 rounded-lg border border-line bg-surface p-5 sm:p-7">
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">2. Confirm & start</p>

            <label className="block text-sm">
              <span className="text-muted">Provider</span>
              <input
                required
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                placeholder="e.g. Comcast"
                className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
              />
            </label>

            <label className="mt-4 block text-sm">
              <span className="text-muted">Phone number to call</span>
              <input
                required
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+1 555 123 4567"
                className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
              />
              <span className="mt-1 block text-xs text-muted">
                From your bill. Orion never dials a number it looked up itself.
              </span>
            </label>

            <label className="mt-4 block text-sm">
              <span className="text-muted">What kind of account is this?</span>
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
              >
                {(playbooks ?? []).map((p) => (
                  <option key={p.vertical} value={p.vertical}>
                    {p.display_name}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-muted">
                Picks the playbook: which desk to ask for, which arguments land. Set from your bill when it can be read from it.
              </span>
            </label>

            <label className="mt-4 block text-sm">
              <span className="text-muted">Call language</span>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="mt-1 w-full rounded border border-line bg-paper px-3.5 py-2.5 text-[14px] text-ink transition-colors focus:border-accent"
              >
                {CALL_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-xs text-muted">
                Orion holds the whole call in this language.
              </span>
            </label>

            <button
              type="submit"
              disabled={starting}
              className="mt-6 w-full rounded bg-accent px-4 py-2.5 text-[13px] font-medium text-accent-ink hover:bg-accent-hover disabled:opacity-40"
            >
              {starting ? "Starting…" : "Start negotiation"}
            </button>
            {startError && <p className="mt-3 text-sm text-partial">{startError}</p>}
          </form>
        </FadeIn>
      </div>
    </div>
  );
}

function money(value: number | null, currency: string | null): string {
  if (value == null) return "-";
  const symbol = currency === "USD" || !currency ? "$" : `${currency} `;
  return `${symbol}${value.toFixed(2)}`;
}

/** Everything the extraction found, and an honest warning when the document
 * isn't the kind of bill anyone can negotiate down. */
function ExtractionSummary({ extraction }: { extraction: BillExtraction }) {
  // Annotated on the literal, not on the filtered result: filtering a
  // string[][] widens the tuple and the annotation no longer applies.
  const all: [string, string][] = [
    ["Provider", extraction.provider],
    ["Monthly rate", money(extraction.current_rate, extraction.currency)],
    ["This statement", money(extraction.amount_due, extraction.currency)],
    ["Account number", extraction.account_number ?? "-"],
    ["Account holder", extraction.account_holder_name ?? "-"],
    ["Plan", extraction.plan_details ?? "-"],
    ["Billing period", extraction.billing_period ?? "-"],
    ["Due", extraction.due_date ?? "-"],
    ["Contract ends", extraction.contract_end_date ?? "-"],
    ["Customer since", extraction.customer_since ?? "-"],
  ];
  const rows = all.filter(([, value]) => value && value !== "-");

  return (
    <div className="mt-6 border-t border-line pt-6">
      {!extraction.is_negotiable && (
        <p className="mb-5 rounded border border-partial/40 bg-partial/10 px-4 py-3 text-[13px] leading-relaxed text-ink-soft">
          This looks like a{" "}
          <span className="text-ink">{extraction.document_type.replace(/_/g, " ")}</span> rather
          than a recurring bill. Orion negotiates ongoing service charges and medical bills - a
          one-off purchase has nothing to reduce. You can still continue if you think that&rsquo;s
          wrong.
        </p>
      )}

      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 border-b border-line pb-2">
            <dt className="text-[13px] text-muted">{label}</dt>
            <dd className="tabular text-right text-[13px] text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      {extraction.line_items.length > 0 && (
        <div className="mt-6">
          <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
            Itemised charges
          </p>
          <ul className="mt-3 space-y-1.5">
            {extraction.line_items.map((item, index) => (
              <li key={index} className="flex justify-between gap-4 text-[13px]">
                <span className="text-ink-soft">{item.description}</span>
                <span className="tabular flex-none text-ink">
                  {money(item.amount, extraction.currency)}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[12px] leading-relaxed text-muted">
            Often waived even when the base rate will not move.
          </p>
        </div>
      )}

      {extraction.notes && (
        <p className="mt-5 text-[13px] leading-relaxed text-ink-soft">{extraction.notes}</p>
      )}
    </div>
  );
}
