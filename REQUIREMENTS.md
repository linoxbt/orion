# Requirements

Everything Orion needs, what each thing unlocks, and how to get it.

Read the first section before spending any money. Most of Orion runs on free
tiers, and the one paid dependency is narrower than it looks.

---

## Contents

- [What works without paying anything](#what-works-without-paying-anything)
- [Why a phone line is still needed for a real call](#why-a-phone-line-is-still-needed-for-a-real-call)
- [Per-user settings, not environment variables](#per-user-settings-not-environment-variables)
- [Required: the four keys Orion cannot start without](#required-the-four-keys-orion-cannot-start-without)
- [Optional: real outbound calls](#optional-real-outbound-calls)
- [Optional: escalation channels](#optional-escalation-channels)
- [Plans and payments](#plans-and-payments)
- [Reference: the full variable list](#reference-the-full-variable-list)
- [Checking your configuration](#checking-your-configuration)

---

## What works without paying anything

With only the four required keys below, all of which have free tiers, you get:

- Sign-in
- Bill upload and extraction from a photo, PDF, screenshot or scan
- The full negotiation agent, over your browser microphone
- Live transcripts, playbooks, consent, receipts, renewals and the account page
- Persistence in Postgres

That covers the whole product except one thing: Orion dialling the company
itself.

## Why a phone line is still needed for a real call

This is worth being precise about, because the two paths are easy to conflate.

**The browser path (free).** Orion opens your microphone, streams the audio to
AssemblyAI's Voice Agent API, and talks. It is the complete agent: the same
playbook, the same voice, the same counters, the same live transcript. What it
does **not** do is reach the provider. There is nobody on the other end except
whoever is sitting at your computer. It is a rehearsal, and it is genuinely
useful for hearing what Orion will say before it says it to a company, but it
does not negotiate your bill on its own.

**The telephone path (needs a carrier).** For Orion to ring a real company on a
real phone number, something has to place that call on the public telephone
network. A web browser cannot do this. It has no access to the phone network at
all, and no browser API exists that would let a web page dial a landline.

**Can AssemblyAI do it instead?** No. AssemblyAI is the agent's brain: speech
recognition, the language model and the voice, all inside one WebSocket. It has
no telephony product and cannot dial a number. Their own documentation describes
the Voice Agent API as working "with Twilio, LiveKit, and any telephony
provider", and their official outbound-call example is a Twilio bridge, where
Twilio's Calls API dials and its Media Streams carries the audio while
AssemblyAI runs the conversation. That is exactly the shape Orion already
implements.

So the choice is not "Twilio or browser". It is:

| | Reaches the provider | Cost |
| --- | --- | --- |
| Browser rehearsal | No, you play the representative | Free |
| Real outbound call | Yes | A carrier account |

**A free middle option.** If you dial the provider yourself on a phone, put it
on speaker next to your computer and run a rehearsal, Orion will hear the
representative through your microphone and negotiate out loud through your
speakers. It costs nothing and needs no carrier. Expect some echo, and expect to
press the phone menu keys yourself, since Orion cannot send tones down a line it
did not dial. It is a workaround, not the designed path, but it works.

**On Twilio trial accounts.** A trial account cannot use `<Stream>` or
`<Record>`, and Orion needs both: `<Stream>` carries the live audio to the
agent, and `<Record>` produces the recording that the post-call verification
reads the outcome from. So a trial cannot place an Orion call at all. If you are
not upgrading, use the browser path. Nothing else in the product is affected.

Twilio is not the only option. LiveKit SIP, Telnyx, Vonage, Plivo and
SignalWire all carry G.711 μ-law at 8kHz, which is what Orion already speaks in
both directions. Twilio is simply what is wired up today.

## Per-user settings, not environment variables

Some things belong to a person, not to the deployment. These are set by each
user on the **Account** page in the app, and there is no environment variable
for them:

| Setting | Where | What it does |
| --- | --- | --- |
| WhatsApp number for alerts | Account page | Where **that user** is messaged when their call stalls |
| Email for alerts | Account page | Same, by email. Falls back to their account email |
| Name, address, phone | Account page | Answers a representative's verification questions |
| Default call language | Account page | Preselected on every new negotiation |

The `ESCALATION_WHATSAPP_TO` and `ESCALATION_EMAIL_TO` variables still exist,
but only as a fallback for a single-user or local deployment. In a multi-user
deployment they should be left unset: they would otherwise page one address
about every customer's call, and disclose the provider and best offer from
negotiations belonging to strangers.

---

## Required: the four keys Orion cannot start without

### 1. `ASSEMBLYAI_API_KEY`

Runs the voice agent and transcribes the recording afterwards. One key covers
the Voice Agent API, streaming transcription, pre-recorded transcription and the
LLM Gateway.

1. Go to [assemblyai.com](https://www.assemblyai.com) and create an account.
2. Open the [dashboard](https://www.assemblyai.com/dashboard/api-keys).
3. Copy the key shown under **Your API key**.

Free tier includes credit to start. The Voice Agent API needs a payment method
on file even while you are inside the free allowance.

### 2. `GEMINI_API_KEY`

Reads the bill. This job needs a multimodal model because the input is a photo
or PDF, which is why it is not done through the LLM Gateway.

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Sign in with a Google account.
3. **Create API key**, choose a project, copy the key.

Free tier is generous and sufficient for bill extraction.

### 3. `ADMIN_API_KEY`

Not obtained from anywhere. You invent it. It gates every privileged route, and
the frontend's copy must match the backend's exactly.

```bash
python -c "import secrets; print('orion-' + secrets.token_urlsafe(32))"
```

Set the same value as `ADMIN_API_KEY` on **both** the backend and the frontend.

### 4. `ACCOUNT_ENCRYPTION_KEY`

Encrypts the account details a customer gives Orion to answer verification
questions. Also generated, not obtained:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Leave it unset and the vault refuses to store anything, which means Orion cannot
answer "what are the last four digits on the account?" and most real calls end
there.

### Also required, but not secret

| Variable | Value |
| --- | --- |
| `DYNAMIC_ENVIRONMENT_ID` | From [dynamic.xyz](https://app.dynamic.xyz) → your project → **Developers → SDK & API Keys → Environment ID**. Also set as `NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID` on the frontend. **Leave it unset and the backend falls back to trusting a header, which turns `ADMIN_API_KEY` into a universal impersonation token.** |
| `ALLOWED_ORIGINS` | Your frontend's real URL, e.g. `https://orionbuild.netlify.app` |
| `BASE_URL` | Your backend's public URL. Must be reachable from the internet if you use telephony, because it is what the carrier is given for webhooks |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | See below |

### Database (strongly recommended)

Without both of these, Orion falls back to a local SQLite file with no backups.

1. Create a project at [supabase.com](https://supabase.com).
2. **Project Settings → API**.
3. `SUPABASE_URL` is the **Project URL**.
4. `SUPABASE_SERVICE_KEY` is the **`service_role`** key, listed under Project
   API keys. It is the secret one, not `anon` / publishable.

The service key bypasses row-level security, which is deliberate here: identity
comes from Dynamic rather than Supabase Auth, so `auth.uid()` is null in that
database and both tables are deny-all by design. **It must only ever be set on
the backend.** Putting it in a frontend environment exposes it to the browser
and grants full read and write on every table.

---

## Optional: real outbound calls

Skip this entirely if you are using the browser path.

### `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`

1. Create an account at [twilio.com](https://www.twilio.com/try-twilio).
2. Both values are on the [console dashboard](https://console.twilio.com) under
   **Account Info**.
3. Reveal the auth token and copy it.

### `TWILIO_PHONE_NUMBER`

1. In the console, **Phone Numbers → Manage → Buy a number**.
2. Filter for **Voice** capability.
3. Buy it, then copy it in E.164 form, e.g. `+15551234567`.

A number costs roughly $1 to $2 per month plus per-minute call charges. You must
upgrade past the trial for `<Stream>` and `<Record>`, which Orion requires.

### After buying a number

Nothing to configure in the Twilio console. Orion sets its own webhook URLs on
each call from `BASE_URL`, and validates `X-Twilio-Signature` against the exact
URL it supplied.

---

## Optional: escalation channels

These carry the message. **Who receives it is set per user on the Account
page**, not here.

### WhatsApp, through Twilio

Needs the Twilio credentials above.

1. In the console: **Messaging → Try it out → Send a WhatsApp message**.
2. Follow the sandbox join step, or request a production WhatsApp sender.
3. Set `TWILIO_WHATSAPP_FROM` to that number in E.164 form. Orion adds the
   `whatsapp:` prefix itself.

The Twilio trial includes 100 free WhatsApp messages.

### Email, through SendGrid

1. Create an account at [sendgrid.com](https://signup.sendgrid.com).
2. **Settings → Sender Authentication** and verify a single sender address.
   Unverified senders are rejected.
3. **Settings → API Keys → Create API Key**, choose **Restricted Access** with
   **Mail Send** permission only.
4. `SENDGRID_API_KEY` is the key. `ESCALATION_EMAIL_FROM` is the verified
   sender.

Free tier is 100 emails a day.

### `PUBLIC_APP_URL`

Your frontend URL, used to build the link back into the app in those messages.
Without it the message arrives with no link.

---

## Plans and payments

Orion meters bills, not calls. A **bill** is the unit: extraction, the
negotiation it produces, and every call on it come out of one allowance.

| Plan | Bills per month | Price |
| --- | --- | --- |
| Free | 5, resetting on the 1st | nothing |
| Unlimited | no limit | $15 a month |

### Why Paystack and not Stripe

**Stripe does not support Nigerian merchants.** A Nigerian business cannot hold
a Stripe account, so the subscription runs on
[Paystack](https://paystack.com) - which Stripe owns, and which covers Nigeria,
Ghana, Kenya, South Africa and Cote d'Ivoire.

### `PAYSTACK_SECRET_KEY`

1. Sign in at [dashboard.paystack.com](https://dashboard.paystack.com).
2. **Settings → API Keys & Webhooks**.
3. Copy the **Live Secret Key** (`sk_live_...`).

### The webhook is not optional

Set the dashboard's **Live Webhook URL** to:

```
https://<backend-host>/api/plan/webhook
```

That webhook is the **only** thing that grants a paid plan. A browser returning
from the payment page is a claim, not proof, so the account changes only when
Paystack tells the server directly, or when the server asks Paystack to verify
a reference itself.

The callback URL may be left as-is: Orion sends its own per transaction, which
overrides the dashboard's. Do not give it a query string of its own - Paystack
appends `?trxref=..&reference=..` verbatim, and two query strings run together.

### Card payments

A new Paystack account usually cannot take cards until compliance is complete,
and the checkout then offers bank transfer, USSD and direct bank only. Card is
already first in `PAYSTACK_CHANNELS`, and Paystack ignores a channel an account
lacks, so **card appears on its own the moment it is enabled** - no deploy
needed.

To check what your account can actually take:

```bash
curl -s https://api.paystack.co/transaction/initialize \
  -H "Authorization: Bearer $PAYSTACK_SECRET_KEY" -H "content-type: application/json" \
  -d '{"email":"you@example.com","amount":100000,"currency":"NGN","channels":["card"]}'
```

`"No active channel to process transaction"` means card is not enabled yet.
Complete **Compliance** in the dashboard, then contact Paystack support.

### Optional: the per-negotiation success fee

`STRIPE_SECRET_KEY` charges a share of a verified saving, separately from the
subscription. It is unavailable to Nigerian merchants, and where it is unset
the charge button is hidden rather than offered and failing.

## Reference: the full variable list

### Backend

| Variable | Status | Unlocks |
| --- | --- | --- |
| `ASSEMBLYAI_API_KEY` | required | The voice agent and verification |
| `GEMINI_API_KEY` | required | Bill extraction |
| `ADMIN_API_KEY` | required | Every privileged route |
| `ACCOUNT_ENCRYPTION_KEY` | required | The verification vault |
| `DYNAMIC_ENVIRONMENT_ID` | required | Verified sessions. Unset is an impersonation hole |
| `ALLOWED_ORIGINS` | required | CORS |
| `BASE_URL` | required for calls | Carrier webhooks |
| `SUPABASE_URL` | recommended | Persistence |
| `SUPABASE_SERVICE_KEY` | recommended | Persistence. Backend only, never a frontend |
| `TWILIO_ACCOUNT_SID` | optional | Real calls |
| `TWILIO_AUTH_TOKEN` | optional | Real calls |
| `TWILIO_PHONE_NUMBER` | optional | Real calls |
| `TWILIO_WHATSAPP_FROM` | optional | WhatsApp escalation |
| `SENDGRID_API_KEY` | optional | Email escalation |
| `ESCALATION_EMAIL_FROM` | optional | Verified SendGrid sender |
| `PUBLIC_APP_URL` | optional | Links inside escalation messages |
| `STRIPE_SECRET_KEY` | optional | Per-negotiation success fee. Unavailable to Nigerian merchants |
| `PAYSTACK_SECRET_KEY` | for paid plans | The $15/month subscription |
| `PAYSTACK_CURRENCY` | has a default | `NGN` |
| `PRO_PRICE` | has a default | Whole units of the currency above |
| `PAYSTACK_CHANNELS` | has a default | Checkout methods, in order |
| `PAYSTACK_PLAN_CODE` | has a default | Pin a plan, or let one be created |
| `ESCALATION_WHATSAPP_TO` | fallback only | Single-user deployments. Leave unset in multi-user |
| `ESCALATION_EMAIL_TO` | fallback only | As above |
| `VOICE_BACKEND` | has a default | `agent_api` or `stt_gemini` |
| `ASSEMBLYAI_VOICE` | has a default | Agent voice id |
| `GEMINI_MODELS` | has a default | Extraction fallback chain |
| `LLM_GATEWAY_MODEL` | has a default | Structured post-call jobs |
| `NEGOTIATION_LLM` | has a default | Which model holds the negotiation |
| `DATABASE_PATH` | has a default | SQLite path when Supabase is unset |

### Frontend

| Variable | Status | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | required | Backend URL, inlined into the browser bundle |
| `ADMIN_API_KEY` | required | **Server only.** Never prefix with `NEXT_PUBLIC_` |
| `NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID` | required | Public by design |
| `API_URL` | optional | Overrides the upstream for server-side routes only |

Do **not** set `ASSEMBLYAI_API_KEY`, `GEMINI_API_KEY` or `SUPABASE_SERVICE_KEY`
on the frontend. Nothing there reads them, and they would be shipped to the
browser or sit needlessly in a build environment.

---

## Checking your configuration

```bash
curl -s https://<backend-host>/health/capabilities \
  -H "X-Orion-Admin-Key: $ADMIN_API_KEY"
```

```json
{"capabilities":{
  "sessionsVerifiable": true,
  "persistence": "supabase",
  "hasAssemblyAI": true,
  "voiceBackend": "agent_api",
  "hasGemini": true,
  "hasTwilio": false,
  "hasStripe": false
}}
```

| Field | Meaning |
| --- | --- |
| `sessionsVerifiable: false` | Every signed-in request will be rejected. Reported separately because a forged token answers `invalid_session` whether the signing keys were fetched or not, so a 401 alone cannot tell the two apart |
| `persistence: "sqlite"` | Supabase is not fully configured. On a container platform this data lasts only as long as the disk |
| `hasTwilio: false` | Expected if you are using the browser path. Rehearsal is unaffected |
