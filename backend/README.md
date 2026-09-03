# Orion backend

FastAPI service behind Orion, the AI agent that calls companies and negotiates a
customer's bill down. It ingests a bill, collects a signed authorization, places
the outbound call, holds the negotiation, and then verifies from the recording
what was actually agreed before any success fee is charged.

The voice layer runs on **AssemblyAI**.

## Architecture

```
Twilio Media Stream (8kHz mu-law)
   |
   +-- VOICE_BACKEND=agent_api ---> AssemblyAI Voice Agent API
   |                                 STT + LLM + TTS + turn detection + tools,
   |                                 one websocket, mu-law in and out
   |
   +-- VOICE_BACKEND=stt_gemini --> AssemblyAI Universal-3.5 Pro streaming STT
                                    -> negotiation LLM (see NEGOTIATION_LLM)
                                    -> Google Cloud TTS -> back to Twilio

after the call:
   Twilio recording -> /v2/upload -> /v2/transcript (speaker labels + PII redaction)
                    -> webhook -> LLM Gateway extraction -> verified outcome -> Stripe
```

Two voice backends exist on purpose. `agent_api` is the managed pipeline and the
fastest path to a working call; `stt_gemini` is the hand-rolled one, where the
turn loop, barge-in and playback are ours and the negotiating model is
selectable. They share the same prompt, the same tools and the same post-call
verification, so a run of calls can be compared backend to backend.

Audio is never transcoded. Twilio carries 8kHz G.711 mu-law; the Voice Agent API
is configured to speak exactly that on both sides, and Google TTS is asked for
`MULAW` at 8000Hz. The `audioop` resampling this project used to need went away
with the Gemini Live bridge.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env     # then fill it in
uv run uvicorn app.main:app --reload --port 8080
```

## Environment

`.env.example` documents every variable. The ones that decide behaviour:

| Variable | What it does |
|---|---|
| `ASSEMBLYAI_API_KEY` | One key covers the Voice Agent API, streaming, pre-recorded and LLM Gateway. |
| `VOICE_BACKEND` | `agent_api` (default) or `stt_gemini`. |
| `NEGOTIATION_LLM` | `gemini_direct` (default) or `llm_gateway` — which model holds the negotiation on the `stt_gemini` backend. |
| `LLM_GATEWAY_MODEL` | Model for the structured jobs: outcome extraction and turn classification. |
| `ASSEMBLYAI_VOICE` | Voice Agent API voice id. `anna` by default. |
| `ACCOUNT_ENCRYPTION_KEY` | Fernet key sealing the account-verification details. Unset means the vault refuses to store them, and Orion can't answer a rep's verification questions. |
| `BASE_URL` | Must be the public URL Twilio can reach. Webhook signatures are validated against it. |
| `ADMIN_API_KEY` | Gates call-placing, charging, and the AssemblyAI transcript webhook. |

### A note on `NEGOTIATION_LLM`

`gemini_direct` is the default because AssemblyAI's LLM Gateway grants access
per account, and on an account without billing the only reachable model is
`qwen3.5-4b-32k-fast` — which **does not support tool calling** and is too small
to hold a multi-round retention negotiation. It handles the structured work
(extraction, classification) well, which is what `LLM_GATEWAY_MODEL` is used for.

Once the AssemblyAI account can reach a capable model, set
`LLM_GATEWAY_MODEL=gemini-3.6-flash` and `NEGOTIATION_LLM=llm_gateway`. Nothing
else changes.

## Running a call

1. `BASE_URL` must be publicly reachable — deployed, or an ngrok/Cloudflare
   tunnel. Twilio webhooks and the AssemblyAI transcript callback both need it.
2. `POST /api/negotiations/start` creates the session.
3. `POST /api/negotiations/{task_id}/authorization` collects the DocuSign
   authorization. The call is refused with `409 not_authorized` until it's signed.
4. `POST /api/negotiations/{task_id}/call` dials out.
5. `GET /api/negotiations/{task_id}/events` streams the live transcript, the
   offers logged mid-call, and the verification result as server-sent events.

All of these are gated by `X-Orion-Admin-Key`.

### Getting past a real provider line

Orion calls real companies, so it has to survive the two things that stop most
third-party callers before a negotiation ever starts.

**The menu.** A provider answers with an IVR, not a person. The agent has a
`press_keys` tool: DTMF is synthesised in `app/services/dtmf.py` as ordinary
audio and pushed down the same media stream as speech, so the tones reach the
menu without redirecting the call to a `<Play digits="">` verb and tearing the
stream down. `linear_to_ulaw` follows the G.711 reference including the shift to
14 bits, and is checked against stdlib `audioop` across all 65,536 inputs.

**Verification.** The rep asks who is calling before discussing anything. The
account holder supplies the answers once, via
`POST /api/negotiations/{task_id}/account-details` — name on the account,
account number, service address, billing ZIP, security PIN, last four of SSN,
date of birth. All optional; supply what your provider asks for.

Those values are the most sensitive data the product handles, so:

- they are encrypted with Fernet (`ACCOUNT_ENCRYPTION_KEY`) before they touch
  the database, and an unset key makes the endpoint return 503 rather than
  storing them in the clear;
- they are never returned by any read endpoint — `GET .../account-details`
  lists field *names* only;
- they never enter the agent's system prompt. The prompt says which fields are
  available; the agent calls `provide_verification` for one field at a time when
  a rep actually asks. That keeps a value the model was never asked for out of
  its mouth, and puts every disclosure on the call's event timeline.

The agent is also told to stay silent on hold — hold music and recorded
messages are not conversation partners.

## Verification

The recording is the evidence. When a call ends, Twilio posts to
`/telephony/recording`; the recording is downloaded (Twilio's media URLs sit
behind basic auth, which AssemblyAI can't use), re-uploaded to `/v2/upload`, and
submitted to `/v2/transcript` with speaker labels and PII redaction. AssemblyAI
posts back to `/telephony/transcript`, and the transcript goes to LLM Gateway to
extract the outcome, the rates and the confirmation number.

`money_amount` and `number_sequence` are deliberately **not** redacted — they are
the negotiated rate and the confirmation number, which is the entire point.

Anything the extraction can't establish is left for a human:
`POST /api/negotiations/{task_id}/complete` remains the override, and sessions
record whether their outcome came from `assemblyai` or a `human`.

## Tests

```bash
uv run pytest
```

`tests/conftest.py` blanks every integration credential before `app.config` is
imported, so a populated `.env` can't cause a test run to make live billable
calls. That matters most for AssemblyAI: an un-terminated streaming session
bills until the 3-hour cap.
