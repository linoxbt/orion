# Orion on AssemblyAI — what actually ships

The two companion documents in this folder (`full-build-specification.md` and
`technical-architecture-and-build-requirements.md`) were written against Gemini
Live as the voice engine. **That is no longer what Orion runs.** The product
thesis, the market analysis, the compliance posture and the phased scope in
those documents all still hold — the voice layer underneath them changed.

This document describes the system as built.

---

## Why it changed

Gemini Live is a native speech-to-speech model: one websocket in, one websocket
out, with transcription, reasoning and speech synthesis fused inside a single
model. That is elegant, and it is also opaque. Three things Orion needs are hard
to get from it:

1. **A transcript you can prove things with.** The success-fee model only works
   if a negotiated saving can be evidenced. A fused speech-to-speech model gives
   you a conversation, not an auditable, speaker-attributed, redactable record.
2. **Control over the negotiating model.** The hardest part of this product is
   the negotiation strategy, not the audio. Being able to change the model
   holding the call — without changing the audio pipeline — is worth a lot.
3. **Audio that matches the telephone.** Gemini Live wants 16kHz PCM in and
   24kHz PCM out. Phone calls are 8kHz G.711 mu-law. Every call paid a real-time
   resampling tax in both directions.

Rebuilding the voice layer on AssemblyAI addresses all three, and removes code:
the `audioop`-based resampling module is gone entirely, because AssemblyAI's
telephony path is byte-compatible with Twilio's.

---

## The shape of it

```
                       Twilio Voice (outbound call)
                                  |
                       Media Stream: 8kHz mu-law
                                  |
                    backend/app/services/live_bridge.py
                          (picks a voice backend)
                    /                              \
      VOICE_BACKEND=agent_api              VOICE_BACKEND=stt_gemini
                |                                     |
   AssemblyAI Voice Agent API           AssemblyAI Universal-3.5 Pro streaming
   STT + LLM + TTS + turn                            |
   detection + tool calling               negotiation LLM (NEGOTIATION_LLM)
   over one websocket                                |
                |                          Google Cloud TTS (MULAW, 8kHz)
                \                                    /
                 -----------------------------------
                                  |
                    live events -> dashboard (SSE)
                                  |
                          call ends, recording ready
                                  |
      Twilio recording -> /v2/upload -> /v2/transcript
        (universal-3-5-pro, speaker_labels, redact_pii)
                                  |
                   webhook -> LLM Gateway extraction
                                  |
                    verified outcome -> Stripe success fee
```

## Where AssemblyAI does the work

| Job | Product | Where |
|---|---|---|
| Holding the negotiation call | Voice Agent API | `backend/app/services/agent_bridge.py` |
| Transcribing the call live | Universal-3.5 Pro streaming | `backend/app/services/stt_bridge.py` |
| Proving what was agreed | Pre-recorded transcription | `backend/app/services/verification.py` |
| Extracting the outcome | LLM Gateway | `backend/app/services/verification.py` |
| Classifying the live negotiation state | LLM Gateway | `backend/app/services/events.py` consumers |

Orion calls real companies. That means surviving an IVR before a human answers,
and an identity check before the account can be discussed — see "Getting past a
real provider line" in `backend/README.md` for how `press_keys` and
`provide_verification` handle each.

---

## Three decisions worth explaining

### Audio is never transcoded

Twilio Media Streams carry base64 G.711 mu-law at 8kHz. The Voice Agent API is
configured with `audio/pcmu` on **both** `session.input.format` and
`session.output.format`, so payloads are copied across untouched. Setting only
the input is the classic error: the agent then replies in 24kHz PCM that Twilio
cannot play.

On the streaming path the same principle holds — `encoding=pcm_mulaw` at
`sample_rate=8000`, because upsampling phone audio to 16kHz measurably hurts
accuracy — and Google TTS is asked for `MULAW` at 8000Hz so its output needs no
conversion either. One wrinkle: Twilio emits 20ms frames while the streaming API
rejects anything outside 50–1000ms, so frames are coalesced to 100ms.

### The outcome is captured twice, from different angles

Mid-call, the agent calls `log_offer`, `record_confirmation_number` and
`escalate_to_human` (`backend/app/services/call_tools.py`). That is first-hand:
the agent knows what it just heard accepted.

Post-call, the recording is transcribed with speaker labels and PII redaction,
and an LLM extracts the same fields independently. The two are reconciled in
`verification.py`, where the mid-call tool results take precedence and the
transcript fills in what they missed.

`money_amount` and `number_sequence` are deliberately excluded from the
redaction policy list. Redacting them would erase the negotiated rate and the
confirmation number — the entire thing being verified.

Anything the extraction cannot establish stays unverified and goes to a human.
An unverified saving is never billed.

### The negotiating model is a setting, not a dependency

`NEGOTIATION_LLM` selects between `gemini_direct` (google-genai) and
`llm_gateway` (AssemblyAI). The default is `gemini_direct`, because LLM Gateway
access is granted per account: on an account without billing the only reachable
model is `qwen3.5-4b-32k-fast`, which does not support tool calling and is too
small to hold a multi-round retention negotiation. It handles the structured
extraction work well, which is what it is used for.

Conversations are carried in OpenAI-shaped messages regardless of provider, so
the switch is one environment variable.

---

## What still comes from the original documents

Unchanged: the market analysis, the regulatory and compliance posture (limited
authorization, recording consent, AI disclosure, the not-a-debt-collector
distinction), the phased scope, the data model, the strategy-playbook design,
and the success-fee economics.

Changed: Section 5's telephony bridge and negotiation agent rows, Section 2's
Gemini Live row, and the reference implementations in Section 4 of the technical
document. Gemini is still used for multimodal bill extraction from an uploaded
photo or PDF, which LLM Gateway's text-only chat completions cannot do.
