const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export interface HealthCapabilities {
  hasAssemblyAI: boolean;
  voiceBackend: string;
  hasGemini: boolean;
  hasTwilio: boolean;
  hasStripe: boolean;
}

export interface Health {
  ok: boolean;
  version: string;
}

export interface LineItem {
  description: string;
  amount: number | null;
}

export interface BillExtraction {
  provider: string;
  /** "recurring_bill" | "medical_bill" | "retail_receipt" | "other" */
  document_type: string;
  /** False for a one-off purchase receipt - there is nothing recurring to argue down. */
  is_negotiable: boolean;
  account_number: string | null;
  account_holder_name: string | null;
  service_address: string | null;
  current_rate: number | null;
  amount_due: number | null;
  currency: string | null;
  due_date: string | null;
  statement_date: string | null;
  billing_period: string | null;
  call_objective: string;
  objective_summary: string | null;
  merchant_type: string | null;
  plan_details: string | null;
  line_items: LineItem[];
  contract_end_date: string | null;
  customer_since: string | null;
  support_phone: string | null;
  notes: string | null;
}

export interface UserProfile {
  id: string;
  email: string | null;
  full_name: string | null;
  avatar_url: string | null;
  phone: string | null;
  country: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  preferred_language: string;
  escalation_whatsapp: string | null;
  escalation_email: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export type ProfileUpdate = Partial<Omit<UserProfile, "id" | "created_at" | "updated_at">>;

export interface Renewal {
  task_id: string;
  provider: string;
  contract_end_date: string;
  days_remaining: number;
  current_rate: number | null;
  negotiated_rate: number | null;
}

export interface Receipt {
  provider: string;
  previous_rate: number | null;
  new_rate: number | null;
  monthly_saving: number | null;
  annual_saving: number | null;
  confirmation_number: string | null;
  outcome: string | null;
  verified: boolean;
  is_sample: boolean;
  verification_source: string | null;
}

/** Languages Universal-3.5 Pro handles natively, with the ones that also have a
 * native-sounding agent voice listed first. */
export const CALL_LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "nl", label: "Dutch" },
  { code: "sv", label: "Swedish" },
  { code: "tr", label: "Turkish" },
  { code: "hi", label: "Hindi" },
  { code: "vi", label: "Vietnamese" },
  { code: "ar", label: "Arabic" },
  { code: "he", label: "Hebrew" },
  { code: "ja", label: "Japanese" },
  { code: "zh", label: "Chinese" },
];

export interface Playbook {
  vertical: string;
  provider: string | null;
  display_name: string;
  strategy_notes: string;
  trigger_phrases: string[];
  retention_routing: string | null;
}

export type NegotiationStatus = "pending" | "calling" | "completed" | "failed";

export interface NegotiationSession {
  task_id: string;
  provider: string;
  phone_number: string;
  vertical: string;
  status: NegotiationStatus;
  call_sid: string | null;
  outcome: string | null;
  confirmation_number: string | null;
  previous_rate: number | null;
  new_rate: number | null;
  verified: boolean;
  is_sample: boolean;
  fee_amount_cents: number | null;
  stripe_payment_intent_id: string | null;
  authorized: boolean;
  language: string;
  consent_signer_name: string | null;
  consent_version: string | null;
  consent_at: string | null;
  bill: BillExtraction | null;
  voice_backend: string | null;
  offers: Offer[];
  escalated: boolean;
  escalation_reason: string | null;
  recording_url: string | null;
  transcript_id: string | null;
  verification_source: string | null;
}

export interface Offer {
  monthly_rate: number | null;
  description: string;
  accepted: boolean;
}

// Events pushed from the backend while a call is live - see
// backend/app/services/events.py for the publishers.
export type LiveEvent =
  | { type: "status"; status: string; backend?: string; reason?: string }
  // Twilio's own view of the call: ringing, in-progress, completed, busy,
  // no-answer, failed, canceled. The screen follows this rather than assuming
  // a call is live because dialling was accepted.
  | { type: "call_status"; status: string }
  // Who holds the floor right now, reported as it happens rather than
  // inferred from transcripts, which lag the speech they describe.
  | { type: "speaking"; who: "orion" | "rep" }
  | { type: "turn"; speaker: "orion" | "rep"; text: string }
  | { type: "offer"; monthly_rate: number | null; description: string; accepted: boolean }
  | { type: "confirmation"; confirmation_number: string | null; new_rate: number | null }
  | { type: "escalation"; reason: string | null }
  | {
      type: "verification";
      verified: boolean;
      outcome: string | null;
      new_rate: number | null;
      confirmation_number: string | null;
    }
  | {
      type: "stance";
      stance: string;
      has_authority: boolean;
      advice: string;
    }
  | { type: "escalation_sent"; channels: string[] }
  | { type: "error"; message: string };

import { authHeaders } from "./auth-client";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? `request_failed_${res.status}`);
  }
  return res.json();
}

/** True when a failure was the session, not the request - the caller should
 * send the user back to /login rather than showing an error. */
export function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export async function getCapabilities(): Promise<{ capabilities: HealthCapabilities }> {
  const res = await fetch(`/api/capabilities`, { headers: authHeaders() });
  return handle<{ capabilities: HealthCapabilities }>(res);
}

export async function ingestBill(file: File): Promise<BillExtraction> {
  // Same-origin proxy (web/app/api/bills/ingest/route.ts). Calling the backend
  // directly meant a 500 came back without CORS headers, which the browser
  // could only report as "Failed to fetch" - hiding the real cause.
  const form = new FormData();
  form.append("file", file);
  form.append("filename", file.name);
  const res = await fetch(`/api/bills/ingest`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return handle<BillExtraction>(res);
}

export async function listPlaybooks(): Promise<Playbook[]> {
  const res = await fetch(`${API_URL}/api/playbooks`);
  return handle<Playbook[]>(res);
}

export async function startNegotiation(body: {
  provider: string;
  phone_number: string;
  vertical: string;
  /** ISO code. Universal-3.5 Pro transcribes 18 languages natively, so this
   * mainly picks the agent's voice and tells it what to speak. */
  language?: string;
  /** The extracted bill. Passing it is what lets the agent quote the
   * customer's real rate and line items on the call instead of guessing. */
  bill?: BillExtraction | null;
}): Promise<NegotiationSession> {
  // Same-origin proxy (web/app/api/negotiations/start/route.ts), not the backend directly - it
  // holds the admin key that gates the real backend's session-creation endpoint, so the key never
  // ends up in this browser bundle. Only creates the session - see placeCall below for actually
  // dialing out, which requires authorization first (build spec Section 3).
  const res = await fetch(`/api/negotiations/start`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<NegotiationSession>(res);
}

export async function getNegotiation(taskId: string): Promise<NegotiationSession> {
  // Same-origin proxy (web/app/api/negotiations/[taskId]/route.ts) - same reasoning as
  // startNegotiation above: the admin key stays server-side.
  const res = await fetch(`/api/negotiations/${taskId}`, { headers: authHeaders() });
  return handle<NegotiationSession>(res);
}

export async function listNegotiations(): Promise<NegotiationSession[]> {
  // Same-origin proxy (web/app/api/negotiations/route.ts) - same reasoning as
  // startNegotiation above: the admin key stays server-side.
  const res = await fetch(`/api/negotiations`, { headers: authHeaders() });
  return handle<NegotiationSession[]>(res);
}

export async function completeNegotiation(
  taskId: string,
  body: { outcome: string; previous_rate?: number; new_rate?: number; confirmation_number?: string }
): Promise<NegotiationSession> {
  // Same-origin proxy (web/app/api/negotiations/[taskId]/complete/route.ts) - same reasoning as
  // startNegotiation above: the admin key stays server-side.
  const res = await fetch(`/api/negotiations/${taskId}/complete`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<NegotiationSession>(res);
}

export async function chargeNegotiation(taskId: string): Promise<NegotiationSession> {
  // Same-origin proxy (web/app/api/negotiations/[taskId]/charge/route.ts) - same reasoning as
  // startNegotiation above: the admin key stays server-side.
  const res = await fetch(`/api/negotiations/${taskId}/charge`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handle<NegotiationSession>(res);
}

export async function placeCall(taskId: string): Promise<NegotiationSession> {
  // Same-origin proxy (web/app/api/negotiations/[taskId]/call/route.ts) - same reasoning as
  // startNegotiation above: the admin key stays server-side. Requires the session to already be
  // authorized (consent is recorded via recordConsent) - the backend returns
  // 409 "not_authorized" otherwise.
  const res = await fetch(`/api/negotiations/${taskId}/call`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handle<NegotiationSession>(res);
}

export interface BrowserSession {
  token: string;
  session: Record<string, unknown>;
}

/** Mint a single-use token and get the agent config to open a browser session.
 *
 * Twilio's trial tier blocks the <Stream> verb, so there is no phone path on a
 * free account. This runs the identical agent over the browser's microphone. */
export async function createBrowserSession(taskId: string): Promise<BrowserSession> {
  const res = await fetch(`/api/browser/${taskId}/session`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
  });
  return handle<BrowserSession>(res);
}

/** Run a tool the agent called, server-side against the real session. */
export async function runAgentTool(
  taskId: string,
  name: string,
  args: Record<string, unknown>
): Promise<{ result: string }> {
  const res = await fetch(`/api/browser/${taskId}/tool`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify({ name, arguments: args }),
  });
  return handle<{ result: string }>(res);
}

/** Put a finished turn on the shared live feed, so a browser call renders the
 * same way a phone call does. */
export async function recordAgentTranscript(
  taskId: string,
  speaker: "orion" | "rep",
  text: string
): Promise<void> {
  await fetch(`/api/browser/${taskId}/transcript`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify({ speaker, text }),
  }).catch(() => {
    // The feed is a convenience; losing a line must not end the call.
  });
}

export interface AccountDetails {
  account_holder_name?: string;
  account_number?: string;
  service_address?: string;
  billing_zip?: string;
  security_pin?: string;
  last4_ssn?: string;
  date_of_birth?: string;
}

export async function saveAccountDetails(
  taskId: string,
  body: AccountDetails
): Promise<NegotiationSession> {
  // Write-only by design. The backend encrypts these on receipt and never
  // returns them; on a call the agent reads one field at a time through a tool.
  const res = await fetch(`/api/negotiations/${taskId}/account-details`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<NegotiationSession>(res);
}

export async function listAccountDetails(taskId: string): Promise<{ fields: string[] }> {
  // Field names only - the values never leave the backend.
  const res = await fetch(`/api/negotiations/${taskId}/account-details`, {
    headers: authHeaders(),
  });
  return handle<{ fields: string[] }>(res);
}

/** Record in-app authorisation to act as the customer's representative.
 *
 * Consent is genuinely required before calling a company about someone's
 * account. Requiring DocuSign for it was not: with DocuSign unconfigured,
 * `authorized` could never become true, so the call button never rendered and
 * no call could ever be placed. */
export async function recordConsent(
  taskId: string,
  body: { signer_name: string; agreed: boolean }
): Promise<NegotiationSession> {
  const res = await fetch(`/api/negotiations/${taskId}/consent`, {
    method: "POST",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<NegotiationSession>(res);
}

/** End a call that is still running.
 *
 * The End button used to close the window and leave the call up. */
export async function hangUpCall(taskId: string): Promise<NegotiationSession> {
  const res = await fetch(`/api/negotiations/${taskId}/hangup`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handle<NegotiationSession>(res);
}

export function subscribeToNegotiationEvents(
  taskId: string,
  onEvent: (event: LiveEvent) => void
): () => void {
  // Read with fetch + a stream reader rather than EventSource. EventSource
  // can't set headers, which would force the session token into the query
  // string - and tokens in URLs end up in access logs and referrers. This
  // keeps it in an Authorization header like every other call.
  const controller = new AbortController();
  let attempt = 0;

  const read = async (): Promise<void> => {
    try {
      const res = await fetch(`/api/negotiations/${taskId}/events`, {
        headers: authHeaders({ accept: "text/event-stream" }),
        signal: controller.signal,
      });
      // 401/404 are terminal - retrying won't fix a session or an id.
      if (res.status === 401 || res.status === 404) return;
      if (!res.ok || !res.body) throw new Error(`feed unavailable (${res.status})`);
      attempt = 0;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;  // server closed; the retry below reconnects
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line; anything after the last
        // separator is a partial frame and stays in the buffer.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          for (const rawLine of frame.split("\n")) {
            if (!rawLine.startsWith("data:")) continue;
            try {
              onEvent(JSON.parse(rawLine.slice(5).trim()) as LiveEvent);
            } catch {
              // A malformed frame shouldn't tear down a live transcript.
            }
          }
        }
      }
    } catch {
      // Aborting on unmount lands here, and so does a dropped connection -
      // which is not the same thing. A call can outlive its feed, so a drop
      // reconnects rather than silently leaving a live transcript frozen.
      if (controller.signal.aborted) return;
    }

    if (controller.signal.aborted) return;
    // Back off, but stay responsive: a call is usually short.
    const delay = Math.min(1000 * 2 ** attempt++, 15000);
    await new Promise((resolve) => setTimeout(resolve, delay));
    if (!controller.signal.aborted) await read();
  };

  void read();

  return () => controller.abort();
}

export async function listRenewals(): Promise<Renewal[]> {
  const res = await fetch(`/api/renewals`, { headers: authHeaders() });
  return handle<Renewal[]>(res);
}

/** A shareable record of a verified saving. Public by design and deliberately
 * thin - no phone number, no account details, no transcript. */
export async function getReceipt(taskId: string): Promise<Receipt> {
  const res = await fetch(`${API_URL}/api/receipts/${taskId}`);
  return handle<Receipt>(res);
}

/** The signed-in customer's own details. Scoped server-side to the verified
 * Dynamic user - the id is never taken from the request body. */
export async function getProfile(): Promise<UserProfile> {
  const res = await fetch(`/api/profile`, { headers: authHeaders() });
  return handle<UserProfile>(res);
}

export async function saveProfile(update: ProfileUpdate): Promise<UserProfile> {
  const res = await fetch(`/api/profile`, {
    method: "PUT",
    headers: authHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(update),
  });
  return handle<UserProfile>(res);
}


// ---- Plan and billing ------------------------------------------------------

export interface PlanState {
  plan: "free" | "pro";
  unlimited: boolean;
  limit: number | null;
  used: number;
  remaining: number | null;
  month: string;
  price_usd: number;
  expires_at: string | null;
  can_upgrade: boolean;
  /** Whether Paystack will charge again, so a renewal is never a surprise. */
  renews: boolean;
  next_payment_at: string | null;
  subscription_status: string | null;
}

export async function getPlan(): Promise<PlanState> {
  const res = await fetch("/api/plan", { headers: authHeaders() });
  return handle<PlanState>(res);
}

/** Opens a payment and returns the page to send the customer to. */
export async function startUpgrade(): Promise<{ authorization_url: string; reference: string }> {
  const res = await fetch("/api/plan/upgrade", { method: "POST", headers: authHeaders() });
  return handle<{ authorization_url: string; reference: string }>(res);
}

/** Stop the plan renewing. The month already paid for is kept. */
export async function cancelPlan(): Promise<PlanState> {
  const res = await fetch("/api/plan/cancel", { method: "POST", headers: authHeaders() });
  return handle<PlanState>(res);
}

/** Checks a payment on the way back from the payment page.
 *
 * The reference is verified server-side against Paystack - this call is a
 * prompt to go and check, not a claim that the payment happened. */
export async function confirmUpgrade(reference: string): Promise<PlanState> {
  const res = await fetch(`/api/plan/confirm?reference=${encodeURIComponent(reference)}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handle<PlanState>(res);
}
