# Orion — Full Build Specification
### An AI Agent That Negotiates Your Bills Down, For a Cut of the Savings

> **Note on the voice engine.** This specification names Gemini Live as the model
> holding the negotiation call. The shipped system runs that layer on AssemblyAI
> instead — see [`assemblyai-architecture.md`](./assemblyai-architecture.md).
> The product thesis, market analysis, compliance posture, phased scope, data
> model and success-fee economics below are unchanged; the swap also let the
> verification service in Section 9 become automated rather than a human review
> queue.

---

## 1. Executive Summary

Orion is an autonomous voice agent that calls companies on a consumer's behalf — cable providers, medical billing departments, subscription services, landlords — and negotiates lower rates, fee waivers, or debt reductions using the same retention/hardship levers a professional bill negotiator would use, but at near-zero marginal cost per call. The business only gets paid when it wins: a percentage of verified savings.

This document is a full build spec for taking Orion from hackathon prototype to a real, revenue-generating product inside a 90-day window, aligned with what the Build with Gemini XPRIZE actually rewards: verified real-world revenue, AI-native operations built on Google Cloud, and category impact (Money & Financial Access).

The honest framing up front: the hard part of this product isn't the AI — Gemini Live can hold a competent negotiation conversation today. The hard part is everything around it — authentication as an authorized party on someone else's account, proving a negotiated outcome actually happened, handling a live call gracefully when it goes sideways, and doing all of this at a cost structure where a success fee still makes sense. That's what most of this spec is about.

---

## 2. Market Analysis & Opportunity

**The pain point, sized:** U.S. households collectively hold hundreds of billions of dollars in "negotiable" recurring costs — cable/internet, cell phone plans, medical bills, subscription services, auto/home insurance premiums, and even rent. Multiple industry studies on human bill-negotiation services estimate the *average successful negotiation* saves a customer $10–$50/month on recurring bills, or hundreds to thousands of dollars on one-time medical bills.

**Why now, not five years ago:** Three things had to be true simultaneously, and only now are:
1. Voice AI good enough to hold an unscripted, adaptive phone conversation with a human retention agent (Gemini Live's low-latency, tool-using voice reasoning).
2. Cheap enough per-call cost that a success-fee model pencils out even on a $10/month savings win.
3. A public willingness to have an AI agent act as your representative on a phone call — a norm that's shifted meaningfully in the last two years.

**Target segments, roughly in order of go-to-market ease:**
- **Subscription/telecom renegotiation** (cable, internet, cell phone, streaming bundles) — highest volume, most standardized retention scripts, lowest call complexity, fastest to prove out.
- **Medical bill negotiation** — higher dollar value per win, more emotionally resonant, but requires deeper domain grounding (chargemaster data, charity-care policy) — see companion idea "Fair Shake" in the broader ideas doc; Orion can absorb this as a vertical once the core negotiation engine is proven.
- **Insurance premium renegotiation, gym memberships, storage units** — secondary verticals once the core loop and trust layer are validated.

**Competitive landscape:**
- *Human bill-negotiation services* (Billshark, BillCutterz, Experian BillFixer via Experian Boost) — the closest existing competitors. They typically charge 30–50% of first-year savings, operate with human negotiators, and have real brand trust and existing merchant relationships. Their weakness: slow (days, not minutes), can't scale, limited to a fixed list of participating companies rather than any company you name.
- *DIY negotiation scripts/communities* (r/personalfinance-style advice) — free, but require the user to actually make the call themselves, which is the exact friction Orion removes.
- *Rocket Money / subscription-cancellation apps* — solve a different, adjacent problem (finding and canceling subscriptions), not negotiation. Worth watching as a potential channel partner or acquirer, not just a competitor.

Orion's structural advantage over the incumbents isn't "AI is cheaper" — it's that AI-per-call cost approaches zero, which means it can profitably pursue *smaller* savings wins (a $8/month cell phone plan reduction) that aren't worth a human negotiator's time, dramatically expanding the addressable pool of winnable negotiations.

---

## 3. Regulatory & Compliance Considerations

*(This is general informational analysis to guide product design, not legal advice — a real launch needs review by a telecom/consumer-finance attorney before placing live calls at scale.)*

- **Authorization to act on the account.** Most companies (Comcast, Verizon, hospitals) will not discuss account details with a third party unless that party is an authorized user/representative on the account or presents a valid Limited Power of Attorney or written consent. The product needs an explicit **consent and authorization flow** at signup — the user grants Orion documented authority to act as their representative for the specific call, ideally with a recorded or e-signed authorization artifact the agent can reference or produce if the company's rep asks for proof.
- **Call recording consent.** Roughly a dozen U.S. states are "two-party consent" states requiring all parties on a call to be notified if it's recorded. Since Orion needs a transcript/recording to verify outcomes, the system should default to an on-call disclosure ("this call may be recorded for quality and verification purposes") regardless of state, both for compliance and for user trust.
- **AI voice disclosure.** Several states have moved toward requiring disclosure when a consumer (or a company representative) is interacting with an AI system rather than a human, and this area is actively evolving. The safest default is to have the agent identify itself as an AI representative acting on the customer's behalf at the start of the call, rather than attempting to pass as human — this also sidesteps a wholly different set of legal and reputational risks.
- **Not a debt collector.** Orion negotiates *on behalf of* the consumer to reduce what they owe or pay going forward — this is meaningfully different from third-party debt collection (regulated under the FDCPA), which involves collecting a debt *from* a consumer on behalf of a creditor. Worth confirming this distinction holds with counsel once the medical-billing vertical is in scope, since collections-adjacent rules can get nuanced there.
- **Payment handling / success-fee billing.** Charging a percentage of "savings" requires a clean, auditable definition of the baseline and the verified new rate — this has PCI-DSS implications the moment you store or process card data directly (favor a PCI-compliant processor like Stripe over building payment storage in-house).
- **Data privacy on uploaded bills.** Bills contain account numbers, sometimes partial SSNs (medical bills especially) — treat this as sensitive financial data requiring encryption at rest and in transit, and minimal retention.

---

## 4. Product Spec — Phased Scope

### Phase 1 — MVP (Weeks 1–6, hackathon build window)
- Single vertical: **cable/internet/cell phone bill renegotiation** (highest call-script standardization, fastest to a working demo).
- Web app: upload or photograph a bill → Gemini extracts provider, current rate, plan details.
- User completes a lightweight authorization flow (e-signed limited authorization + call-recording consent).
- Agent places the call via Gemini Live + telephony bridge, executes a negotiation playbook for that specific provider, and produces a call summary.
- Verification: agent captures the confirmation number and new-rate confirmation email/SMS from the provider as documentary evidence.
- Success-fee billing triggers automatically once the next bill arrives showing the reduced rate (or immediately, off the confirmation, at a discount, with a refund-if-wrong policy).
- Support for 5–10 major providers' playbooks (top cable/telecom companies by market share) to start.

### Phase 2 — Expansion (Weeks 7–10)
- Add a second vertical: medical bill negotiation (higher value per case, justifies more manual playbook curation).
- Human-escalation path: if the AI agent hits a wall (rep refuses, requests info the agent can't verify, gets aggressive), seamlessly hand off to a human operator mid-call rather than failing silently.
- Build the "strategy playbook" content pipeline — a semi-automated system for researching and encoding a new company's retention offers, competitor pricing, and known discount tiers, so playbook creation scales without a human researching each company from scratch every time.

### Phase 3 — Trust & Scale (Weeks 11–13)
- Public "savings leaderboard"/social-proof layer for growth (with user permission) — "Orion saved users $X this month."
- Dispute-resolution process for the rare case a user disputes the verified savings amount (see Section 9 and the GenLayer discussion in Section 12 for one approach to this).
- Referral program, since this product benefits enormously from word-of-mouth ("it saved my mom $40/month on Comcast").

---

## 5. System Architecture

**High-level flow:**

```
User (web/mobile) 
   → Bill Ingestion Service (Gemini multimodal extraction)
   → Authorization & Consent Service (e-sign + recording disclosure)
   → Negotiation Orchestrator (Cloud Run)
        → Strategy Engine (Gemini + Vertex AI Search over playbook corpus)
        → Telephony Bridge (Twilio Voice + Gemini Live API)
        → Live Call Session (real-time voice reasoning, tool-calling)
   → Verification Service (parses confirmation evidence, flags for review if ambiguous)
   → Billing Service (Stripe success-fee capture)
   → Analytics Layer (BigQuery)
```

**Core components:**

| Component | Role | Primary tech |
|---|---|---|
| Bill Ingestion | Extract provider, current rate, account details from a photo/PDF/upload | Gemini multimodal (Document AI for structured cases) |
| Authorization Service | Collect e-signed limited authorization + recording consent | Cloud Run + e-sign integration (e.g., DocuSign API) |
| Strategy Engine | Given provider + account details, retrieve the right negotiation playbook and generate a call plan | Gemini 2.x reasoning + Vertex AI Search (RAG) over a maintained playbook corpus |
| Telephony Bridge | Places outbound call, streams audio bidirectionally | Twilio Voice (or comparable) ↔ Gemini Live API |
| Negotiation Agent | Holds the live call: navigates IVR, reaches a rep, executes the negotiation, adapts to pushback, escalates to human on failure | Gemini Live API with function-calling (retrieve pricing data, check escalation authority, log transcript in real time) |
| Verification Service | Confirms the win actually happened (confirmation number, follow-up email/SMS, next-bill cross-check) | Gemini document parsing + rules engine; human-in-the-loop queue for ambiguous cases |
| Billing Service | Charges the success fee once verified | Stripe |
| Data Layer | Session state, playbooks, transcripts, outcomes | Firestore (transactional state), Cloud Storage (recordings/documents), BigQuery (analytics) |

---

## 6. Data Model (core entities)

- **User** — identity, contact info, linked accounts, authorization documents on file.
- **Bill/Account** — provider, account number (encrypted), current rate, plan details, baseline snapshot.
- **NegotiationSession** — links a User + Bill to a call attempt: status, transcript reference, outcome, escalation history.
- **StrategyPlaybook** — per-provider (or per-vertical) negotiation knowledge: known discount tiers, retention offers, competitor pricing benchmarks, effective phrasing/angles, common objections and counters.
- **Outcome** — verified before/after rate, evidence artifacts (confirmation number, email, next bill), verification status (auto-verified / pending review / disputed).
- **Payment** — success fee amount, trigger event, processor reference.

---

## 7. The Negotiation Strategy Engine (the actual hard part)

This is the component that determines whether Orion is "an AI chatbot with a phone" or a real negotiation engine, and it deserves the most design attention.

**Playbook structure per provider:** known published discount tiers, typical retention-offer ladder (what a rep is authorized to offer at tier 1 vs. what requires asking for a supervisor), competitor pricing to cite as leverage, and known "trigger phrases" that unlock better offers (e.g., "I'm considering canceling" often routes a call to a retention team with more authority than general customer service).

**Escalation ladder within a single call:** the agent should never accept the first offer reflexively — it should be designed to push through at least 2–3 rounds (initial offer → cite competitor pricing/loyalty tenure → request supervisor/retention specialist) before settling, mirroring what a skilled human negotiator does.

**Failure handling:** IVR navigation failure, disconnected calls, reps who refuse to negotiate, or reps who ask for information the agent doesn't have — all of these need clean fallback paths (retry, human takeover, or a clear "we couldn't get a better rate" outcome that still respects the user's time).

**Guardrails:** the agent must never misrepresent facts about the user's situation, never impersonate the account holder as a human, and must operate within the specific authorization scope the user granted — these aren't just compliance requirements, they're what makes the "AI representative" framing sustainable rather than a one-time trick that gets companies to start blocking these calls.

---

## 8. 90-Day Build Timeline (team of 2–4)

| Weeks | Milestone | Suggested ownership |
|---|---|---|
| 1–2 | Architecture setup, Twilio↔Gemini Live integration proof-of-concept, first playbook (one provider) hand-built | Backend/infra lead |
| 3–4 | Bill ingestion + authorization flow; first successful end-to-end test call | Full-stack + one negotiation-content owner |
| 5–6 | 5–10 provider playbooks live; first real user pilot calls; verification pipeline v1 | Whole team |
| 7–8 | First paying customers; refine escalation ladder based on real call failures | Whole team, weighted toward negotiation-engine iteration |
| 9–10 | Human-escalation handoff built; begin medical-billing vertical playbook research | Split: 1 on core product, 1–2 on vertical expansion |
| 11–12 | Scale outreach/distribution; instrument full analytics/KPI dashboard | Growth-focused member + data |
| 13 | Polish, demo prep, revenue/impact documentation for submission | Whole team |

---

## 9. Trust & Verification Layer

The single biggest business risk isn't "can the AI negotiate" — it's **"can you prove it worked, cheaply, at scale, in a way both the user and your payment processor trust."**

A pragmatic verification stack:
1. **In-call evidence** — capture the confirmation number and the rep's verbal confirmation of the new rate as part of the transcript.
2. **Documentary evidence** — request the company auto-send a confirmation email/SMS (standard practice for most retention calls) and parse it.
3. **Next-bill cross-check** — for recurring bills, confirm the new rate appears on the subsequent statement before finalizing the fee (or charge a smaller amount upfront with an automatic true-up).
4. **Human review queue** — any outcome that doesn't cleanly auto-verify (ambiguous evidence, user dispute) routes to manual review rather than either auto-charging or auto-refunding.

This is deliberately the simplest version of a verification system that could work. Section 12 discusses a more sophisticated, trust-minimized alternative using GenLayer, and why I'd hold off on it for the hackathon build.

---

## 10. Go-to-Market

- **Wedge:** start with cable/internet/cell phone bills specifically, since retention scripts are the most standardized and public (Reddit/DoNotPay-style communities already document exact phrasing that works on major carriers) — this makes playbook-building tractable in week one rather than week six.
- **Distribution:** personal-finance communities (relevant subreddits, TikTok "save money" creator partnerships), a simple referral incentive (both parties get a discounted fee on their next negotiation), and a "free savings check" lead magnet (upload your bill, see your estimated savings potential, before committing to the paid negotiation).
- **Trust-building for a first-time user:** transparency is the entire pitch — show the actual call transcript, the actual before/after rate, and only charge on verified success. This directly counters the natural skepticism of "why would I let an AI call my cable company."

---

## 11. Financial Model (illustrative, for planning — not a guarantee)

Rough unit economics to sanity-check the model (all figures illustrative, to be replaced with real pilot data as soon as available):

- Average successful negotiation saves a user an estimated **$15–$30/month** on a recurring bill.
- At a **25% success fee** on first-year annualized savings, a single win might generate roughly **$45–$90** in one-time revenue per successful negotiation.
- Per-call cost (telephony minutes + Gemini Live usage) is a small fraction of that revenue, meaning the model can remain profitable even on smaller wins that wouldn't justify a human negotiator's time — this is the core structural bet of the business.
- Success rate assumptions should be pressure-tested early and often; if fewer than roughly 1 in 3 attempted negotiations succeed, the funnel economics (marketing cost to acquire a user who uploads a bill) need re-examination.

---

## 12. Risk Analysis

- **Company pushback/blocking.** Once large telecoms notice a pattern of AI-driven negotiation calls, they may start training reps to detect and deflect them, or blocking known caller IDs — mitigate with rotating numbers, natural pacing, and an agent design that doesn't announce itself in a way that triggers a scripted deflection (while still being honest per the AI-disclosure guardrail above).
- **Negotiation failure rate.** Real success rates will likely be lower and more variable than any hackathon demo suggests — build the pilot phase specifically to get an honest read on this before scaling spend.
- **Telephony/voice reliability.** IVR systems are inconsistent and sometimes actively hostile to non-human callers (some already use voice-based CAPTCHAs) — this is a real, not hypothetical, engineering risk to budget time for.
- **Regulatory drift.** AI-voice disclosure law is moving fast; build the disclosure step as a configurable, easily-updated component rather than hardcoding assumptions.
- **Trust/reputation risk.** A single bad outcome (a botched call that damages a user's account standing, or a disputed charge) could disproportionately hurt a young brand — the human-escalation and dispute-resolution paths in Sections 7 and 9 exist specifically to contain this.

---

## 13. Metrics & KPIs to Track From Day One

- Calls attempted vs. calls that reached a human rep (IVR navigation success rate)
- Negotiation success rate, by provider
- Average verified savings per successful negotiation
- Time-to-verification (how long between call and confirmed outcome)
- Revenue per user, cost per call, contribution margin per successful negotiation
- User-reported trust/satisfaction (would they let the agent call again)

---

## 14. Demo Script for Hackathon Judging

1. **Open with the problem, fast** — a real, relatable bill (cable or a medical bill) on screen, 10 seconds, no more.
2. **Live call, unscripted** — a judge or a pre-arranged real account provides a real bill; the agent places a real call live in the room.
3. **Let the friction show** — don't over-edit; a moment of the agent navigating an IVR menu or handling a "let me check with my supervisor" moment is more convincing than a too-smooth call.
4. **Land the number** — end on the confirmed new rate, side by side with the old one, and the success fee charged live.
