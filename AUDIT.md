# Audit status

The findings from the 2026-09-05 audit, and what happened to each. Severities
are the audit's own. Anything still open says why, and whose it is to close.

## Closed

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| B1 | Critical | An LLM round trip ran inside the loop that forwards audio to Twilio, so every representative turn stopped the call's audio for the length of an HTTP request | Stance classification runs as a held background task (`agent_bridge.py`), covered by `test_live_call_latency.py` |
| B2 | High | The live transcript appended the replay buffer again on every reconnect, so a normal call showed each turn four or five times | Per-call sequence numbers (`events.py`), dropped client-side in `lib/api.ts`, covered by `lib/live-events.test.ts` |
| B3 | High | A 401 was swallowed, leaving the dashboard and account pages on their loading state permanently | `useSessionExpiry` clears the session and redirects, covered by `lib/use-session-expiry.test.tsx` |
| B4 | High | Three concurrent writers each held a stale copy of the whole session document; the last save erased the others, including a confirmation number logged mid-call | `store.mutate` re-reads inside a per-negotiation lock; webhooks, tools and verification all use it. `test_concurrent_writes.py` |
| B5 | High | A completed call could sit reading "Pending" forever, because the bridge's teardown beat the status webhook | The webhook promotes from PENDING as well as CALLING. `test_call_outcomes.py` |
| B6 | Medium | A recording was filed against the newest attempt rather than the dial it came from | The call SID travels with it (`telephony.py`, `verification.py`) |
| B7 | Medium | A negotiation that was refused was shown as a failed call, identical to a number that never connected | Status says whether the call ran; `verified` says whether it won |
| B8 | Medium | The SQLite fallback filtered by user after `LIMIT 100`, so a user could see an empty dashboard | Scoped in SQL |
| B9 | Low | A negotiation from before per-dial attempts showed "No calls yet" beside a recording that existed | `_legacy_attempts` synthesises the one call |
| B10 | Medium | Tool results were held for the turn and dropped on a barge-in, leaving the API waiting on an answer it had asked for | Always delivered, and after two seconds delivered regardless |
| S1 | High | The admin sign-in accepted unlimited guesses, unthrottled and unlogged | Five per address per fifteen minutes, and every failure logged. `test_admin_session.py` |
| S2 | Medium | The operator cookie *was* `ADMIN_API_KEY` | A signed, expiring session token derived from it |
| S3 | Medium | Any signed `charge.success` carrying a user id granted a month of Pro, whatever it was for | The charge must cover the plan price in the plan's currency. `test_payment_amount.py` |
| S4 | Medium | The upload size was checked after the whole file had been read | Refused on declared size, and the read itself is bounded |
| S5 | Medium | No CSP, no frame-ancestors, no Referrer-Policy on a site holding account details | Added in `netlify.toml` |
| S6 | Low | A public receipt quoted model-written prose from somebody's phone call | It states the figures instead |
| P1 | High | `twilio-python` is synchronous and was awaited inline, stalling the whole process | `asyncio.to_thread` |
| P2 | Medium | One signed URL per attempt, in series, before the call history rendered | `asyncio.gather` |
| P4 | Medium | The outcome extraction - what billing rests on - ran on a 4B model | Gemini first, LLM Gateway as the fallback. `test_outcome_extraction.py` |
| P5 | Low | Subscriber sets outlived the calls they belonged to | Pruned with the replay buffers |
| M1 | Critical | The database schema existed only inside the live Supabase project | `backend/migrations/001_init.sql`, verified by applying it to the live database inside a transaction and rolling back |
| M3 | Medium | `NEXT_PUBLIC_ROOT_DOMAIN` existed only in the Netlify UI, so a rebuild elsewhere silently produced a single-host app | In `netlify.toml` and `.env.example`, and deliberately absent from preview contexts |
| M4 | Medium | No component or page tests at all | 24 of them, on the regressions that actually shipped |
| M5 | Medium | The browser rehearsal ignored `end_call` and held a billable session open | It hangs up, after the goodbye |
| M6 | Low | A dead endpoint, proxy and client for single-recording playback | Removed, coverage moved onto the call list |
| M7 | Low | `CallAttempt.transcript_id` was never written | Written with the transcript |
| M8 | Low | Stale test counts in the docs | Regenerated from the suites |

## Open

| # | Severity | Finding | Why it is still open |
| --- | --- | --- | --- |
| S7 | High | The Paystack live key, the Supabase `service_role` key, the Twilio auth token and a Dynamic API token have all passed through chat | Rotation is the owner's to do: each one is replaced in its own dashboard, and only the owner can sign in there. `/root/.orion-dynamic-token` should be deleted at the same time. |
| M2 | High | `escalate_to_human` cannot deliver anything: no `SENDGRID_API_KEY`, no `TWILIO_WHATSAPP_FROM` | Needs an account this deployment does not have. The product no longer claims otherwise: `/health/capabilities` reports `hasEscalation`, the account page says plainly that nothing will be sent, and the landing page's line was corrected. |
| - | - | No real call has yet held a full conversation end to end | Needs a live call on a funded Twilio account. Everything on that path is tested in isolation and proven against production as far as it can be without one. |
