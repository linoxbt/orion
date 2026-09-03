"use client";

import { useEffect, useState } from "react";
import { getCapabilities, type HealthCapabilities } from "@/lib/api";

const INTEGRATIONS: { key: "hasAssemblyAI" | "hasGemini" | "hasTwilio" | "hasStripe"; label: string; detail: string; envVars: string[] }[] = [
  {
    key: "hasAssemblyAI",
    label: "AssemblyAI",
    detail: "Holds the live call, and transcribes the recording afterwards to verify the outcome",
    envVars: ["ASSEMBLYAI_API_KEY"],
  },
  {
    key: "hasGemini",
    label: "Gemini",
    detail: "Reads the uploaded bill, and reasons during the call on the custom voice backend",
    envVars: ["GEMINI_API_KEY"],
  },
  {
    key: "hasTwilio",
    label: "Twilio",
    detail: "Places the outbound call and carries the audio",
    envVars: ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"],
  },
  {
    key: "hasStripe",
    label: "Stripe",
    detail: "Charges the success fee, only once a saving is verified",
    envVars: ["STRIPE_SECRET_KEY"],
  },
];

export default function SettingsPage() {
  const [health, setHealth] = useState<{ capabilities: HealthCapabilities } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCapabilities()
      .then(setHealth)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  return (
    <div className="max-w-2xl">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Settings</p>
      <h1 className="mt-4 font-display text-[2.4375rem] leading-none text-ink">Integrations</h1>
      <p className="mt-4 max-w-prose text-[14px] leading-relaxed text-ink-soft">
        These are set in the backend&apos;s <code className="font-mono text-accent">.env</code> (copy from{" "}
        <code className="font-mono text-accent">.env.example</code>) - this page just reports what{" "}
        <code className="font-mono text-accent">/health</code> currently sees, it doesn&apos;t let you edit them here.
      </p>

      {error && (
        <div className="mt-8 rounded border border-fail/40 bg-fail/10 px-6 py-6 text-center">
          <p className="font-display text-[1.3875rem] text-fail">Backend unreachable</p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink/70">{error}</p>
        </div>
      )}

      {!health && !error && (
        <div className="mt-8 rounded border border-line bg-surface px-6 py-10 text-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">Loading…</p>
        </div>
      )}

      {health && (
        <>
        {health.capabilities.voiceBackend && (
          <p className="mt-8 rounded border border-line bg-surface-2 px-5 py-3 text-[13px] text-ink-soft">
            Voice backend in use:{" "}
            <span className="font-mono text-[12px] text-accent">{health.capabilities.voiceBackend}</span>
          </p>
        )}
        <div className="mt-5 flex flex-col divide-y divide-line rounded-lg border border-line bg-surface">
          {INTEGRATIONS.map((integration) => {
            const configured = health.capabilities[integration.key] ?? false;
            return (
              <div key={integration.key} className="flex items-start justify-between gap-6 px-6 py-5">
                <div className="min-w-0">
                  <p className="text-[14px] font-medium text-ink">{integration.label}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{integration.detail}</p>
                  <p className="mt-2 font-mono text-[10px] text-muted">{integration.envVars.join(", ")}</p>
                </div>
                <span
                  className={`shrink-0 rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] ${
                    configured ? "bg-pass/10 text-pass" : "bg-muted/10 text-muted"
                  }`}
                >
                  {configured ? "Configured" : "Not configured"}
                </span>
              </div>
            );
          })}
        </div>
        </>
      )}
    </div>
  );
}
