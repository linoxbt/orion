"""Read the room, mid-call.

A negotiation is not a script; it is a series of positions. A representative
who has just softened wants pressing, and one who has hardened wants a
different angle rather than the same request repeated louder - which is exactly
what a model with no sense of the other side's stance will do.

Each finished representative turn is classified through AssemblyAI's LLM
Gateway. The classification is published to the live feed so the dashboard
shows where the call stands, and folded back into the agent's context so the
next thing it says accounts for it.

The model here is doing short structured classification, not negotiating, so
the small fast model on LLM Gateway is genuinely the right tool rather than a
compromise.
"""

import logging

from app.services.assemblyai import llm_gateway_json

logger = logging.getLogger(__name__)

STANCES = ("gatekeeping", "refusing", "hedging", "softening", "conceding", "hostile")

_PROMPT = """You are watching one side of a live negotiation call. Given what the company's \
representative just said, classify their position.

Return ONLY a JSON object:
  "stance": one of gatekeeping, refusing, hedging, softening, conceding, hostile
  "has_authority": true if this person can actually approve a discount or refund, false if \
they are front-line staff who would need to transfer
  "advice": one short sentence telling the negotiator what to do next, in the imperative

Guidance: "gatekeeping" means they are deflecting to another department or process. \
"hedging" means non-committal. "softening" means they have started looking for options. \
"conceding" means an actual offer is on the table."""

# What to do about each stance, if the classifier gives no better advice.
FALLBACK_ADVICE = {
    "gatekeeping": "Ask directly for the retention or cancellations team.",
    "refusing": "Acknowledge the refusal, then ask what would need to be true for it to change.",
    "hedging": "Ask a closed question that forces a yes or no.",
    "softening": "Press now - name the specific figure you want.",
    "conceding": "Log the offer, then ask if that is the best available before accepting.",
    "hostile": "De-escalate, thank them, and ask to speak with a supervisor.",
}


async def read_stance(rep_said: str) -> dict[str, object] | None:
    """Classify one representative turn. Returns None rather than raising - a
    failed classification must not interrupt a live call."""
    if len(rep_said.strip()) < 12:
        # Too short to carry a position; "one moment" is not a stance.
        return None

    try:
        result = await llm_gateway_json(
            [
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": rep_said},
            ],
            max_tokens=200,
        )
    except Exception as exc:  # noqa: BLE001 - never break a call over this
        logger.warning("Stance classification failed: %s", exc)
        return None

    if not result:
        return None

    stance = str(result.get("stance", "")).lower()
    if stance not in STANCES:
        return None

    advice = str(result.get("advice") or "").strip() or FALLBACK_ADVICE[stance]
    return {
        "stance": stance,
        "has_authority": bool(result.get("has_authority", False)),
        "advice": advice,
    }


def coaching_note(reading: dict[str, object]) -> str:
    """The line pushed back into the agent's context before its next turn."""
    stance = reading["stance"]
    note = f"[Read of the room: the representative is {stance}. {reading['advice']}]"
    if not reading["has_authority"]:
        note += " [They likely cannot approve this themselves - consider asking for the team that can.]"
    return note
