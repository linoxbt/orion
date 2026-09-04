# Orion

An AI agent that calls your service providers and negotiates your bills down.

Upload a bill. Orion reads the provider, your rate and the plan straight off it,
then holds a real phone conversation with that company: it waits through hold
music, presses the right menu keys, asks for retention by name, states your
case, and counters the first offer. Afterwards it transcribes its own recording
and reports only what that recording actually supports.

Built on [AssemblyAI](https://www.assemblyai.com) for the live voice agent and
the post-call verification pass.

**Live:** [orionbuild.netlify.app](https://orionbuild.netlify.app)

---

## Contents

- [Why it exists](#why-it-exists)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Running it locally](#running-it-locally)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Security model](#security-model)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Current status](#current-status)

Setting it up? **[REQUIREMENTS.md](REQUIREMENTS.md)** lists every key, what it unlocks, and step by step how to get it.

---

## Why it exists

Providers price on inertia. The advertised rate for a new customer is routinely
lower than what a long-standing one pays, and the difference is recovered only
by asking, usually after being transferred to a retention desk holding discounts
the first agent cannot see. Most people never make that call. Orion is the part
that does.

## How it works

| Stage | What happens |
| --- | --- |
| **Extract** | The bill is read by Gemini's multimodal model. Provider, current rate, plan, account number and contract end date come off the document. Unreadable fields are left blank rather than guessed. |
| **Review** | Everything extracted is shown back as editable fields. The agent argues from these numbers, so a wrong rate makes a wrong argument. |
| **Verify** | Account details the provider will ask for are encrypted with Fernet before storage and used only to answer a verification question on the call. |
| **Authorise** | One consent per negotiation, never blanket. The wording, the name and the timestamp are stored so what was authorised can be reconstructed. |
| **Call** | Twilio dials out and bridges the audio to AssemblyAI's Voice Agent API over a WebSocket. The transcript streams to the browser live over SSE. |
| **Verify the outcome** | The recording is transcribed afterwards and the result read back out of it. A saving the transcript does not support is never recorded and never billed. |
| **Follow up** | A verified saving produces a shareable receipt. The contract end date drives a renewal reminder about six weeks before the promotional rate lapses. |

**Plans.** Five bills a month free, resetting on the 1st; 50 cents a month for
unlimited. A bill is the unit - extraction, the negotiation and its calls all
come out of one allowance. Payment runs on Paystack, and a paid plan is granted
only by Paystack's signed webhook or by the server verifying a reference
itself, never by the browser reporting success.

There are two ways to run a negotiation:

- **Rehearsal** runs the identical agent over your microphone with you playing
  the representative. Same playbook, same voice, same counters. It dials nobody
  and costs nothing, and it works with no phone line configured.
- **The real call** dials the provider. It requires consent, a configured phone
  line, and a negotiation that has not already been called. The UI names which
  of the three is missing rather than hiding the button.

A browser cannot reach the public telephone network, and AssemblyAI has no
telephony product, so dialling a company needs a carrier. Everything else works
without one. See [REQUIREMENTS.md](REQUIREMENTS.md#why-a-phone-line-is-still-needed-for-a-real-call).

## Architecture

```
  Browser (Next.js 15, App Router)
      |
      |  same-origin /api/* proxy routes
      |  (hold ADMIN_API_KEY, forward the Dynamic bearer token)
      v
  FastAPI backend  ────────────────>  AssemblyAI Voice Agent API   (live call)
      |     |                          AssemblyAI transcription     (verification)
      |     |                          Gemini                       (bill extraction)
      |     └──────────────────────>  Twilio                        (telephony)
      v
  Supabase (Postgres) or SQLite fallback
```

**Why the browser never calls the backend directly for privileged routes.** The
admin key can place a real phone call and charge a real card, so it lives only
in the Next.js server runtime. Each proxy route verifies the caller's Dynamic
session first, then attaches the key. It also removes CORS from the picture: a
500 from the backend arrives without CORS headers, so a cross-origin browser
call surfaces it as an opaque "Failed to fetch" rather than the real error.

**Voice backends.** `VOICE_BACKEND=agent_api` (the default) runs the whole agent
over one AssemblyAI WebSocket. `stt_gemini` composes streaming STT, an LLM and
Google TTS instead, and exists for when finer control over the turn loop is
worth the extra moving parts.

## Running it locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
git clone https://github.com/linoxbt/orion.git
cd orion

# Backend
cd backend
cp .env.example .env          # fill in the keys listed below
uv sync
uv run uvicorn app.main:app --reload --port 8080

# Frontend, in a second terminal
cd web
cp .env.example .env.local    # ADMIN_API_KEY must match the backend's
npm install
npm run dev                   # http://localhost:3000
```

The minimum to get a working rehearsal is `ASSEMBLYAI_API_KEY`,
`GEMINI_API_KEY`, `ADMIN_API_KEY` and `ACCOUNT_ENCRYPTION_KEY`. Telephony,
billing and Supabase are all optional, and an unconfigured integration reports
itself as unconfigured rather than failing obscurely.

Generate the encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Configuration

### Backend

| Variable | Required | Purpose |
| --- | --- | --- |
| `ASSEMBLYAI_API_KEY` | yes | Voice Agent API, transcription and LLM Gateway. One key covers all three. |
| `GEMINI_API_KEY` | yes | Bill extraction. Multimodal, so LLM Gateway's text-only chat completions cannot do this job. |
| `ADMIN_API_KEY` | yes | Gates every privileged route. Must match the frontend's exactly. |
| `ACCOUNT_ENCRYPTION_KEY` | yes | Fernet key for the verification-detail vault. Unset means the vault refuses to store anything, and most real calls end at verification. |
| `DYNAMIC_ENVIRONMENT_ID` | yes | Session tokens are verified against Dynamic's JWKS. **Leave it unset and the backend falls back to trusting a header, which makes `ADMIN_API_KEY` a universal impersonation token.** |
| `ALLOWED_ORIGINS` | yes | CORS allowlist. Set to the real frontend URL in production. |
| `BASE_URL` | for calls | Public URL Twilio is given for webhooks. Must be reachable from the internet. |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | for calls | Outbound telephony. Without them, rehearsal still works. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | recommended | Persistence. **Both** are required; with only one set the app falls back to SQLite. Use the `service_role` secret key, never the publishable one, and never expose it to a browser. |
| `GEMINI_MODELS` | no | Ordered fallback chain for extraction. A single pinned model is a liability: Gemini returns "high demand" for minutes at a time and retrying the same one is futile. |
| `VOICE_BACKEND` | no | `agent_api` (default) or `stt_gemini`. |
| `STRIPE_SECRET_KEY` | no | Per-negotiation success fee. Unavailable to Nigerian merchants, and the charge button is hidden without it. |
| `PAYSTACK_SECRET_KEY` | for paid plans | The $0.50/month subscription. Stripe cannot be used by a Nigerian business; Paystack is Stripe-owned and covers the region. |
| `TWILIO_WHATSAPP_FROM` / `SENDGRID_API_KEY` / `ESCALATION_*` | no | How you are reached when the agent hits a wall mid-call. An unconfigured channel is skipped, never raised, because a failed notification must not take down a live call. |

### Frontend

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Backend URL, inlined into the browser bundle. |
| `API_URL` | Overrides the upstream for server-side proxy routes only, for when the backend is reachable at a different address from inside the platform's network. |
| `ADMIN_API_KEY` | **Server-only.** Never prefix with `NEXT_PUBLIC_`. |
| `NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID` | Dynamic environment id. Public by design. |

AssemblyAI and Gemini keys are deliberately **not** frontend variables. They
belong to the backend, and putting them in the web environment would ship them
to the browser without adding any capability.

## Deployment

The backend runs on Railway from a Dockerfile, and the frontend on Netlify.

```bash
# Backend - run from the repository root, not from backend/.
# The service's root directory is /backend, and running from inside it
# fails with "railpack prepare exited with an error".
railway up --service backend --detach

# Frontend
cd web && netlify deploy --build --prod
```

`netlify.toml` sets `base = "web"` because the Next.js app is not at the
repository root.

After deploying, confirm the backend can actually verify sessions:

```bash
curl -s https://<backend-host>/health/capabilities -H "X-Orion-Admin-Key: $ADMIN_API_KEY"
# {"capabilities":{"sessionsVerifiable":true, ...}}
```

`sessionsVerifiable: false` means every signed-in request will be rejected. It
is reported separately because a forged token answers `invalid_session` whether
the signing keys were fetched or not, so a 401 alone cannot tell the two apart.

## Security model

Three layers, deliberately distinct:

- **`require_admin_key`** proves a request came from our own server-side proxy
  rather than straight off the internet. It says nothing about who the request
  is for.
- **`require_user_id`** establishes *which person* the request is for, by
  verifying their Dynamic session token against Dynamic's published keys. Not
  by trusting a header.
- **`require_owned_session`** is the one that protects data: it loads the
  negotiation and refuses unless it belongs to the caller. A negotiation
  belonging to someone else answers `404`, not `403`, because a 403 would
  confirm the id exists.

Also enforced:

- **Twilio webhooks** validate `X-Twilio-Signature` against the exact URL Twilio
  was given, not the observed request URL, which can be wrong behind a proxy.
- **The media stream WebSocket** carries an HMAC token minted when the TwiML is
  built. Twilio cannot sign a WebSocket upgrade, so without this, knowing a task
  id was enough to join a live call and open a billable session.
- **Verification details** are encrypted at rest with Fernet.
- **Rate limits** cover the two endpoints that spend money per call: bill
  extraction and agent-session minting.
- **Receipts are public but thin.** Provider, rates and confirmation number, and
  nothing else. A link forwarded to a friend must not become a way to read a
  stranger's account.

If you find something, open an issue rather than a pull request.

## Testing

```bash
cd backend && uv run pytest        # 250 tests
cd web && npm test                 # 39 tests
cd web && npx tsc --noEmit && npx eslint .
```

`backend/tests/test_authorization.py` is worth reading first. Every case in it
reproduces an attack that worked against a running deployment before the fix:
reading a stranger's negotiation, writing a PIN onto it, consenting on their
behalf, and reaching the call endpoint.

## Project layout

```
backend/
  app/
    routers/      HTTP surface, one module per resource
    services/     AssemblyAI, Twilio, Gemini, Supabase, encryption, escalation
    security.py   the three authorisation layers described above
    playbooks.py  the negotiation strategies, per vertical
  tests/
web/
  app/            Next.js App Router; (shell) is the signed-in area
    api/          server-side proxy routes that hold the admin key
  components/
  lib/            API client, auth helpers, the browser voice agent
docs/             architecture and build specification
```

## Current status

Working and verified in production: authentication, bill extraction, the
rehearsal agent end to end, live transcripts, consent, receipts, renewals and
the account profile.

Not yet exercised end to end, because they need credentials that are not
configured: outbound telephony and its DTMF, recording and verification path;
WhatsApp and email escalation. The code is written and unit tested, but no
real call has been placed end to end.

Card payments are not yet enabled on the connected Paystack account, so the
checkout currently offers bank transfer, USSD and direct bank. Card is already
first in the channel list and appears automatically once Paystack enables it.

Persistence currently falls back to SQLite on a mounted volume, because
`SUPABASE_SERVICE_KEY` is not set on the backend.

## License

MIT. See [LICENSE](LICENSE).

Built for the [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon),
September 2026.
