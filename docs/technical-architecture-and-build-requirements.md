# Orion — Technical Architecture, SDKs & Build Requirements

> **The voice layer described below is no longer what Orion runs.** This document
> specifies Gemini Live as the real-time voice engine; the shipped system runs on
> AssemblyAI — the Voice Agent API and Universal-3.5 Pro streaming for the call,
> pre-recorded transcription and LLM Gateway for post-call verification. See
> [`assemblyai-architecture.md`](./assemblyai-architecture.md) for what is
> actually built and why it changed.
>
> Everything else here — the supporting services, the infrastructure checklist,
> the security notes, the cost model — still applies. Gemini remains in the stack
> for multimodal bill extraction, just not on the call path.

This is the engineering companion to the build spec: the concrete stack, packages, APIs, and accounts you need before writing the first line of code, plus real reference implementations to build from rather than from scratch.

---

## 1. Architecture Overview

```
┌─────────────────┐
│   Web/Mobile     │  Bill upload, authorization e-sign, dashboard
│   Frontend       │  (React/Next.js)
└────────┬─────────┘
         │ HTTPS
         ▼
┌─────────────────────────────┐
│  Application Backend         │  Cloud Run (Python/FastAPI or Node)
│  - Auth (Firebase Auth)      │
│  - Bill ingestion            │──────► Document AI (Invoice Parser)
│  - Session orchestration     │──────► Gemini 2.x / 3.x (reasoning, strategy)
│  - Verification pipeline     │──────► Vertex AI RAG Engine (playbook grounding)
└────────┬─────────────────────┘
         │ triggers outbound call
         ▼
┌─────────────────────────────┐         ┌──────────────────┐
│  Telephony Bridge            │◄───────►│  Twilio Voice /   │
│  (Cloud Run, WebSocket)      │  media  │  Media Streams or │
│                               │  stream │  ConversationRelay│
└────────┬─────────────────────┘         └──────────────────┘
         │ bidirectional audio (WebSocket)
         ▼
┌─────────────────────────────┐
│  Gemini Live API              │  Real-time voice reasoning,
│  (Gemini 3.1 Flash Live)      │  tool-calling, barge-in, transcription
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Data & Ops Layer             │
│  - Firestore (session state)  │
│  - Cloud Storage (recordings, │
│    documents)                 │
│  - BigQuery (analytics)       │
│  - Secret Manager (creds)      │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Stripe (success-fee billing) │
│  DocuSign (authorization docs)│
└─────────────────────────────┘
```

---

## 2. Core Google Cloud / Gemini Stack

| Piece | What it does in Orion | Package / API | Docs |
|---|---|---|---|
| **Gemini Live API** | Holds the real-time negotiation call — native speech-to-speech, barge-in (handles interruptions), tool-calling mid-conversation, live transcription | `google-genai` (Python/JS SDK) or raw WebSocket | ai.google.dev/gemini-api/docs/live-api |
| **Gemini 2.x/3.x (standard)** | Non-realtime reasoning: bill parsing assistance, strategy generation, appeal-style document drafting, playbook research | `google-genai` | ai.google.dev/gemini-api/docs |
| **Agent Development Kit (ADK)** | Orchestration framework for the multi-step pipeline (intake agent → strategy agent → call agent → verification agent) with built-in support for tool use and multi-agent hierarchies | `google-adk` (Python) | google.github.io/adk-docs |
| **Vertex AI RAG Engine / Vertex AI Search** | Grounds the strategy engine in your maintained playbook corpus (per-provider retention offers, competitor pricing) so the agent isn't improvising from general knowledge | Part of Vertex AI SDK; used as an ADK tool (`VertexAiRagRetrieval`) | cloud.google.com/vertex-ai/generative-ai/docs/agent-builder |
| **Document AI — Invoice Parser** | Extracts structured fields (provider, account number, current rate, due date) from an uploaded bill photo/PDF | `google-cloud-documentai` | cloud.google.com/document-ai/docs/processors-list |
| **Firestore** | Session state, user records, negotiation status, playbook versioning | `google-cloud-firestore` | cloud.google.com/firestore/docs |
| **Cloud Storage** | Call recordings, uploaded bill documents, authorization PDFs | `google-cloud-storage` | cloud.google.com/storage/docs |
| **BigQuery** | Aggregate analytics: success rate by provider, average savings, cost per call | `google-cloud-bigquery` | cloud.google.com/bigquery/docs |
| **Secret Manager** | Twilio/Stripe/DocuSign credentials, API keys | `google-cloud-secret-manager` | cloud.google.com/secret-manager/docs |
| **Cloud Run** | Hosts the backend, the telephony bridge, and any scheduled jobs | `gcloud run deploy` (no SDK — deployment target) | cloud.google.com/run/docs |
| **Cloud Scheduler / Cloud Tasks** | Triggers next-bill verification checks, renewal reminders | `google-cloud-tasks` / `google-cloud-scheduler` | cloud.google.com/tasks/docs |

**Install (Python backend example):**
```bash
pip install google-genai google-adk google-cloud-documentai \
  google-cloud-firestore google-cloud-storage google-cloud-bigquery \
  google-cloud-secret-manager google-cloud-tasks
```

**A note on the model itself:** Gemini's Live API model line has moved fast — Gemini 3.1 Flash Live is the current generation as of mid-2026, offering native speech-to-speech (not a stitched-together ASR→LLM→TTS pipeline), affective dialog that adapts tone, and "proactive audio" where the model decides when to speak rather than relying purely on voice-activity detection. It's now generally available on Vertex AI with production SLAs and multi-region failover. Model IDs do churn on the free/developer tier, so pin your model version explicitly in code and check the docs before each deploy rather than assuming a name stays stable.

---

## 3. Telephony Layer — the part that isn't Google's problem to solve

Gemini Live API speaks WebSocket audio natively, but it doesn't place phone calls — you need a telephony provider to bridge a real phone call to that WebSocket stream. Three real paths, in order of how much control you get:

### Option A — Twilio Media Streams (raw bridge, most control)
You run your own WebSocket server (commonly Python/FastAPI or Node) that:
1. Twilio's Voice API places the outbound call.
2. Once connected, Twilio opens a bidirectional Media Stream (WebSocket) to your server.
3. Your server converts audio formats in both directions — **this is the unglamorous but critical detail**: Twilio sends/expects 8kHz μ-law (G.711), while Gemini Live expects 16-bit PCM at 24kHz (16kHz input in some configs). Audio has to be resampled and re-encoded in real time in both directions.
4. Your server relays converted audio to/from the Gemini Live WebSocket session.

This is the most flexible option and the one used in most of the reference implementations below. It requires more integration work but gives full control over call flow, function-calling hooks, and failure handling (dropped calls, IVR navigation).

### Option B — Twilio ConversationRelay (managed, less plumbing)
Twilio's newer product designed specifically to connect a phone call to an LLM over a fast, event-driven WebSocket, handling much of the audio-format complexity for you. Faster to get a working prototype, less control over the low-level audio pipeline. Good for the Phase 1 MVP if you want to save build time and can accept somewhat less control over the call.

### Option C — Google's own partner integrations (Voximplant, Pipecat, Agora, Fishjam)
Google explicitly lists partner platforms that have pre-integrated Gemini Live API over WebRTC to streamline real-time audio/video app development — worth evaluating if you want to avoid building or maintaining the bridge yourself. Voximplant specifically advertises inbound/outbound call connectivity to Live API.

**Recommendation for the 90-day build:** start with Option A (raw Twilio Media Streams) using one of the open reference repos below as a starting skeleton — it's the best-documented path with the most working example code, and it gives you the control you'll need later for the escalation-ladder and human-handoff logic described in the build spec.

**Package:** `pip install twilio`

---

## 4. Reference Implementations Worth Forking

These are real, working repos demonstrating exactly this integration pattern — use them as a skeleton rather than building the Twilio↔Gemini bridge from a blank file:

- **google-gemini/gemini-live-api-examples** (official Google repo) — Gen AI SDK Python examples, raw WebSocket examples, and links to every partner integration (Pipecat, Fishjam, Voximplant, ADK Streaming, Firebase AI SDK).
- **ZackAkil/gemini-live-api-twilio-phone** — minimal, well-documented Cloud Run + Twilio + Gemini Live phone-call demo; a good starting skeleton for Option A.
- **kkrishnan90/Gemini-Live-Twilio-** — a fuller example with a React frontend, FastAPI backend, and outbound-call initiation flow — closer to Orion's actual shape (a UI that triggers an outbound negotiation call).
- **Twilio's own ConversationRelay + Gemini tutorial** (twilio.com/blog) — the Option B managed path, with Python quickstart.
- **AlexITC/twimini-bot** — a Scala/sbt implementation, useful mainly as a second reference for the streaming pipeline design if your team isn't Python-first.

---

## 5. Supporting Third-Party Services

| Service | Role | Package |
|---|---|---|
| **Stripe** | Success-fee billing, triggered post-verification | `pip install stripe` |
| **DocuSign** | E-signed limited authorization + call-recording consent capture | `pip install docusign-esign` (or direct REST) |
| **Firebase Auth** | User identity/login | `firebase-admin` (backend), Firebase JS SDK (frontend) |

---

## 6. Infrastructure & DevOps Requirements Checklist

**Accounts/access to set up before day one:**
- [ ] Google Cloud project with billing enabled
- [ ] Gemini API access (via Google AI Studio for prototyping, or Vertex AI for production SLAs) — note the docs distinguish an "ai.google.dev" developer path (fastest to start) from the Vertex AI enterprise path (production SLAs, data residency, multi-region failover) — start on the former, plan to migrate to the latter before real users
- [ ] APIs enabled: Vertex AI API, Document AI API, Discovery Engine API (powers Vertex AI Search/RAG data stores), Cloud Run API, Firestore API, Cloud Storage API, BigQuery API, Secret Manager API
- [ ] Service account(s) with least-privilege IAM roles scoped per component (the agent's service account should only see what it needs — this is the step most teams under-scope or over-scope, per the docs)
- [ ] Twilio account with a purchased phone number and Voice-enabled
- [ ] Stripe account (test mode first) with Connect/payouts configured if you ever split revenue with playbook contributors
- [ ] DocuSign developer account for e-signature integration
- [ ] Domain + TLS for your Cloud Run services (Cloud Run provides this by default on `*.run.app`, but you'll want a custom domain before real users)

**Environment/secrets to provision (store in Secret Manager, never in code):**
- `GEMINI_API_KEY` (or Vertex AI service account credentials, depending on path chosen)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `STRIPE_SECRET_KEY`
- `DOCUSIGN_INTEGRATION_KEY` + related OAuth credentials
- `BASE_URL` (your public Cloud Run URL or custom domain, needed for Twilio webhooks)

**Security note flagged in Google's own tutorials:** outbound-call trigger endpoints must be authenticated (API key header, internal-traffic restriction, or OAuth) — an unauthenticated "place a call" endpoint is a real, documented footgun (anyone who finds the URL can place calls billed to your account).

---

## 7. Resources Specifically Useful If You're Building With an AI Coding Agent

- **Gemini Live API Skill** — Google publishes a skill file specifically so coding agents (like Claude Code) can learn the Live API's conventions before generating code against it; worth loading if your team is using an AI pair-programmer for this build.
- **ADK docs' "Grounding with Search" and "Vertex AI RAG Engine tool" pages** — these show the exact tool-registration pattern (`VertexAiRagRetrieval`, `VertexAiSearchTool`) you'll use to wire the playbook corpus into the strategy agent.
- **Google's Agent Garden** — a library of sample agents/tools inside Vertex AI Agent Builder; worth browsing for a multi-agent orchestration pattern close to what Section 7 of the build spec describes (strategy → call → verification as separate sub-agents).

---

## 8. Rough Cost Model (for planning, not a quote)

- **Gemini Live API:** priced per audio token; recent public pricing on the Flash Live tier runs roughly $3 per million audio input tokens and $12 per million audio output tokens, which works out to fractions of a cent per minute of conversation — cheap enough that the success-fee model in the build spec holds up even on modest wins. Confirm current pricing before finalizing unit economics, since this has changed with each model generation.
- **Document AI (Invoice Parser):** billed per page processed (order of cents per document, not per page-batch) — trivial at MVP scale.
- **Twilio:** per-minute voice pricing plus phone number rental — this will likely be your largest per-call cost, more than the Gemini usage itself.
- **Stripe:** standard processing fees on the success-fee transaction.
- **DocuSign:** typically a monthly per-seat or per-envelope developer plan.

---

## 9. What to Build First (tying back to the 90-day timeline)

Given this stack, the literal first working milestone should be: **Option A Twilio bridge + Gemini Live, placing one real outbound call that says a scripted opening line and hangs up** — using the ZackAkil or kkrishnan90 repo as a skeleton — before any strategy engine, RAG grounding, or verification logic exists. Get the hardest, least-documented part (real-time audio bridging) working end-to-end first; everything else in the stack (Document AI parsing, ADK orchestration, RAG grounding, Stripe billing) is comparatively well-trodden ground and can be layered in afterward without architectural risk.
