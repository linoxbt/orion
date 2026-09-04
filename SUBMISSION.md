# Hackathon submission

Everything needed for the [AssemblyAI Voice Agent Hackathon](https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon)
submission form, in one place. Copy the fields straight out of here.

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
agent stops mid-sentence when the representative talks over it, and five
JSON-Schema tools it calls during the conversation.

| Tool | What it does |
| --- | --- |
| `log_offer` | Records what the rep put on the table, as it is said |
| `press_keys` | Synthesises DTMF tones to get through the IVR menu |
| `provide_verification` | Releases a single encrypted field, only when asked |
| `record_confirmation_number` | Captures the reference a saving depends on |
| `escalate_to_human` | Messages the customer while the call is still live |

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
cents a month for unlimited. 405 tests across both halves, and two full
security audits with every finding closed.

**Try it**

Application: **orionbuild.netlify.app** · Source: **github.com/linoxbt/orion** (MIT)

---

## Tags

**Technology:** AssemblyAI · Voice Agent API · Universal-3.5 Pro · Realtime STT ·
LLM Gateway · Twilio · Next.js · FastAPI · Supabase · Python · TypeScript

**Category:** Voice Agents · Consumer · FinTech · Automation · Productivity

---

## Video script, 2 minutes 50

Conversational, first person. Read it the way you'd explain it to a friend, not
the way you'd read a press release. Roughly 400 spoken words, which leaves real
silence for the call to actually happen on screen. The pauses are the point,
not dead air to fill.

### 0:00 to 0:22 · The hook

*[Screen: a bill on the desk, or the landing page]*

> So I looked at my internet bill last month and it had gone up. Again. Not by
> much, a few pounds. Not enough to spend forty minutes on hold about.
>
> And that's exactly the business model. They're not overcharging you by so
> much that you'll do something about it. They're overcharging you by *just*
> little enough that you won't.
>
> I got tired of that. So I built something to make the call for me.

### 0:22 to 0:40 · What it is

*[Screen: uploading the bill, extraction filling the fields in]*

> This is Orion. You give it a bill, a photo or a PDF, whatever you've got, and
> it reads it. Provider, what you're paying, what plan you're on, when your
> contract ends.
>
> That last one matters more than you'd think. It's the thing you actually
> negotiate with.

### 0:40 to 1:45 · The call, and let it breathe

*[Screen: authorise, then press Place the call. Let it ring.]*

> I authorise it for this one bill. It won't call anyone I haven't said yes to.
> And then it dials.

*[Pause. Let the ringing play. Don't talk over it.]*

> That's it calling. And this is the bit I still find strange to watch.

*[Let 15 to 20 seconds of the actual conversation play. Say nothing.]*

> It asked for retention. It didn't take the first offer. And when the agent
> talked over it, it stopped mid-sentence. That's real barge-in, not a bot
> finishing its script into somebody's ear.
>
> Everything you're reading there is Universal-3.5 Pro, live, through
> AssemblyAI's Voice Agent API. One connection doing the recognition, the
> language model, and the voice.

### 1:45 to 2:12 · Rehearsal mode

*[Screen: rehearsal mode, you talking into the mic]*

> Before you let it loose on a real company, you can hear exactly what it'll
> say. This is the same agent, same playbook, same tools, running on my
> microphone with me playing the rep.

*[Push back at it once. Let it counter.]*

> No phone line. No cost. Just: here's what it's going to say on your behalf.

### 2:12 to 2:38 · The part I care about most

*[Screen: the receipt, then press play on the recording]*

> Now, an agent that tells you it did well is marking its own homework. So
> Orion doesn't do that.
>
> After the call, the recording goes back through AssemblyAI for transcription,
> and the outcome gets read *out of the transcript*. The new rate. The
> confirmation number. If the recording doesn't back it up, it doesn't count as
> a saving and you're never charged for it.
>
> And you can just listen to it.

*[Play two seconds of the recording.]*

> That's the call. That's what was said for me.

### 2:38 to 2:50 · Close

*[Screen: landing page]*

> Four AssemblyAI products doing four different jobs: the live agent, the
> alternate speech backend, the transcription, and the model that reads the
> result back.
>
> It's live, it's open source, and your bill went up quietly.
>
> Might be worth pushing it back down.

### Notes for the recording

- **Don't narrate over the call.** The silence while it negotiates is the most
  convincing part of the whole video. Resist filling it.
- **One take is fine.** A slightly rough, real recording lands better here than
  a polished one that looks staged.
- **Use your own mobile as the provider number** for the demo call, and say so
  if asked. It demonstrates the pipeline without troubling a real company.
- **If the phone call doesn't work on the day**, cut straight from 0:40 to
  rehearsal mode and say plainly that the phone path is wired and
  signature-verified, and here's the same agent over your microphone. Do not
  imply a call happened that didn't.

---

## Checklist

- [x] Public GitHub repository
- [x] MIT licence
- [x] Application URL
- [x] Title, short and long description
- [x] Technology and category tags
- [ ] Cover image, from slide 1 of the deck
- [ ] Slide presentation, exported from the deck to PDF
- [ ] Video presentation, using the script above
- [ ] Enrolled on lablab.ai and Discord
