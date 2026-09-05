# Hackathon submission

The copy for the [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon)
submission form. Copy the fields straight out of here.

The video script lives separately, in [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md).

**Deadline:** 30 September 2026, 4:00 PM WAT.

---

## Title

> Orion: the phone call you never make

If the form wants a bare product name, use **Orion** and let the short
description carry the line.

---

## Short description

> An AI voice agent that phones your provider and negotiates your bill down,
> then proves the saving from its own call recording.

---

## Long description

**The problem**

Companies price on inertia. The advertised rate for a new customer is routinely
lower than what a long-standing one pays, and the gap is recoverable only by
asking, usually after being transferred to a retention desk holding discounts
the first agent cannot see. It is a fifteen-minute phone call, mostly hold
music, that almost nobody makes twice a year for every bill they own.

**What Orion does**

Upload a bill as a photo or PDF. Orion reads the provider, your current rate,
the plan and the contract end date off the document, then telephones the
company and negotiates on your behalf. It holds through the music, presses the
right menu keys, asks for retention by name, answers the security questions
from an encrypted vault, states your case from your actual figures, and refuses
the first offer. You watch the transcript stream live, and afterwards you can
listen to the call itself.

**How AssemblyAI is used**

Orion uses four AssemblyAI products, and takes both paths the challenge offers
rather than choosing one.

The **Voice Agent API** holds the live call over a single WebSocket:
Universal-3.5 Pro for recognition, LLM routing, and voice output, configured
with the provider's key terms, an interruption-enabled turn detector so the
agent stops mid-sentence when the representative talks over it, and six
JSON-Schema tools it calls during the conversation.

| Tool | What it does |
| --- | --- |
| `log_offer` | Records what the rep put on the table, as it is said |
| `press_keys` | Synthesises DTMF tones to get through the IVR menu |
| `provide_verification` | Releases a single encrypted field, only when asked |
| `record_confirmation_number` | Captures the reference a saving depends on |
| `escalate_to_human` | Messages the customer while the call is still live |
| `end_call` | Says goodbye and hangs up when the conversation is finished |

The **Realtime Speech-to-Text API** powers an alternate voice backend, where
orchestration, turn-taking and speech synthesis are handled independently. It
is selectable at runtime, so the two architectures can be compared on the same
negotiation.

**Pre-recorded transcription** and the **LLM Gateway** do the part that makes
the result trustworthy. An agent that reports its own success is marking its
own homework, so Orion doesn't record an outcome from what it believes
happened. After the call, the recording is transcribed with speaker labels and
the result is read back out of that transcript: the new rate, the confirmation
number, what was actually agreed. A negotiation the recording does not support
stays unverified, is never counted as a saving, and is never billed for.

The call runs in whichever of 18 recognised languages the customer picks, with
agent voices in six.

**Rehearsal mode**

The same agent runs over your microphone with you playing the representative.
The full negotiation, the same playbook and the same tools, with no phone line
required. It is the honest way to hear what Orion will say before it says it to
a company, and it needs no telephony account at all.

**What's built**

A FastAPI backend and a Next.js application, deployed and running: Dynamic
authentication verified server-side against published keys, per-negotiation
ownership on every route, signature-checked telephony webhooks, an HMAC-signed
media stream, Fernet-encrypted verification details, Supabase persistence, call
recordings archived to private storage and served through expiring signed
links, and metered billing on Paystack at five bills a month free or fifty
cents a month for unlimited. 455 tests across both halves, and two full
security audits with every finding closed.

**Try it**

Site: **useorion.xyz** · Application: **app.useorion.xyz** · Docs:
**docs.useorion.xyz** · Source: **github.com/linoxbt/orion** (MIT)

---

## Tags

**Technology:** AssemblyAI · Voice Agent API · Universal-3.5 Pro · Realtime STT ·
LLM Gateway · Twilio · Next.js · FastAPI · Supabase · Python · TypeScript

**Category:** Voice Agents · Consumer · FinTech · Automation · Productivity

---

## Checklist

- [x] Public GitHub repository
- [x] MIT licence
- [x] Application URL
- [x] Title, short and long description
- [x] Technology and category tags
- [ ] Cover image, from slide 1 of the deck
- [ ] Slide presentation, exported from the deck to PDF
- [ ] Video presentation, using [VIDEO-SCRIPT.md](VIDEO-SCRIPT.md)
- [ ] Enrolled on lablab.ai and Discord
