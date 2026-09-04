"""Tools the negotiation agent can call mid-conversation.

Definitions use the Voice Agent API's FLAT tool schema - {type, name,
description, parameters} - not OpenAI's nested {type:"function", function:{...}}
form, which is silently rejected.

Capturing the outcome through tools while the call is still up beats
reconstructing it from the transcript afterwards: the agent knows which offer
it just accepted and what confirmation number it was read. The post-call
transcript pass (app/services/verification.py) then corroborates that rather
than being the only source.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.models import NegotiationSession, Offer
from app.services import account_vault, events, notify
from app.services.dtmf import VALID_KEYS, keys_to_mulaw
from app.store import save_session

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "end_call",
        "description": (
            "End the call. Use this once the conversation is genuinely finished: "
            "the change is agreed and you have read back the confirmation, the "
            "representative has firmly refused and there is nothing further to "
            "ask, or you have been told to call another department or another "
            "time. Say goodbye first, then call this. Do not use it to escape a "
            "difficult moment - a refusal you have not yet countered is not the "
            "end of a call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "One short sentence on why the call is over, for the "
                        "customer's record."
                    ),
                },
            },
            "required": ["reason"],
        },
    },
    {
        "type": "function",
        "name": "log_offer",
        "description": (
            "Record a concrete offer the representative has made. Call this every "
            "time a price or promotion is named, whether or not you accept it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_rate": {
                    "type": "number",
                    "description": "The new monthly rate in USD the rep offered.",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of the offer, e.g. '12 months promotional pricing, same speed tier'.",
                },
                "accepted": {
                    "type": "boolean",
                    "description": "Whether you accepted this offer on the call.",
                },
            },
            "required": ["description"],
        },
    },
    {
        "type": "function",
        "name": "record_confirmation_number",
        "description": (
            "Record the confirmation or reference number for an agreed change, "
            "along with the agreed new monthly rate. Call this once the rep has "
            "confirmed the change is applied to the account."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation_number": {
                    "type": "string",
                    "description": "The confirmation/reference number the rep read out.",
                },
                "new_monthly_rate": {
                    "type": "number",
                    "description": "The agreed new monthly rate in USD.",
                },
            },
            "required": ["confirmation_number"],
        },
    },
    {
        "type": "function",
        "name": "press_keys",
        "description": (
            "Press keys on the phone keypad. Use this to get through an automated "
            "menu - for example press '2' for billing, or '0' to reach an operator. "
            "Listen to the whole menu before pressing. Use a comma for a short pause."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "string",
                    "description": "The keys to press, e.g. '2' or '1,0' or '#'.",
                },
                "reason": {
                    "type": "string",
                    "description": "What the menu offered for this option.",
                },
            },
            "required": ["keys"],
        },
    },
    {
        "type": "function",
        "name": "provide_verification",
        "description": (
            "Look up one account detail the representative has asked for in order "
            "to verify the account, such as the account number or security PIN. "
            "Only call this when the representative explicitly asks for that "
            "detail. Never volunteer these values, and never read out a field you "
            "were not asked for."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": (
                        "One of: account_holder_name, account_number, service_address, "
                        "billing_zip, security_pin, last4_ssn, date_of_birth."
                    ),
                },
            },
            "required": ["field"],
        },
    },
    {
        "type": "function",
        "name": "escalate_to_human",
        "description": (
            "Hand the call off to a human operator. Call this if the rep refuses "
            "outright, becomes hostile, or demands account verification you "
            "cannot provide."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the call needs a human.",
                },
            },
            "required": ["reason"],
        },
    },
]


AudioSink = Callable[[bytes], Awaitable[None]]


async def dispatch(
    session: NegotiationSession,
    name: str,
    arguments: dict[str, Any],
    *,
    audio_sink: AudioSink | None = None,
    on_end_call: Callable[[], Awaitable[None]] | None = None,
) -> str:
    """Runs one tool call and returns the string result to hand back to the agent.

    `on_end_call` hangs up the live call; end_call needs it, and where it is
    absent - the browser rehearsal - the tool still records the outcome and the
    session simply closes normally.

    `audio_sink` puts raw mu-law onto the live call; press_keys needs it and the
    other tools ignore it. Unknown tool names return an error string rather than
    raising: an unrecognised call must not tear down a live phone call.
    """
    if name == "press_keys":
        keys = str(arguments.get("keys", "")).strip()
        if not keys:
            return "No keys given."
        if audio_sink is None:
            return "The keypad isn't available on this call."
        # Refuse a sequence that is mostly junk rather than blasting noise at a
        # menu waiting for one digit.
        if not any(key.upper() in VALID_KEYS for key in keys):
            return f"'{keys}' has no usable keypad digits."

        await audio_sink(keys_to_mulaw(keys))
        events.publish(
            session.task_id,
            {"type": "keypad", "keys": keys, "reason": arguments.get("reason", "")},
        )
        return f"Pressed {keys}."

    if name == "provide_verification":
        field = str(arguments.get("field", "")).strip()
        value = account_vault.unseal(session.account_details).get(field)
        if value is None:
            return (
                f"{field} is not on file for this account. Tell the representative "
                "you don't have that detail available."
            )
        # Recorded as an event so there is an audit trail of what was disclosed
        # on the call. The value itself is never logged.
        events.publish(session.task_id, {"type": "verification_disclosed", "field": field})
        return value

    if name == "log_offer":
        offer = Offer(
            monthly_rate=arguments.get("monthly_rate"),
            description=str(arguments.get("description", "")),
            accepted=bool(arguments.get("accepted", False)),
        )
        session.offers.append(offer)
        await save_session(session)
        events.publish(
            session.task_id,
            {"type": "offer", "monthly_rate": offer.monthly_rate, "description": offer.description,
             "accepted": offer.accepted},
        )
        return "Offer logged."

    if name == "record_confirmation_number":
        session.confirmation_number = str(arguments.get("confirmation_number", "")).strip() or None
        rate = arguments.get("new_monthly_rate")
        if rate is not None:
            session.new_rate = float(rate)
        await save_session(session)
        events.publish(
            session.task_id,
            {"type": "confirmation", "confirmation_number": session.confirmation_number,
             "new_rate": session.new_rate},
        )
        return f"Confirmation number {session.confirmation_number} recorded."

    if name == "end_call":
        # The agent finishing its business and then sitting on an open line is
        # a bill running and a person waiting for it to go away. Ending is the
        # polite thing and the cheap thing.
        reason = str(arguments.get("reason", "")).strip()
        session.outcome = session.outcome or reason or "The call ended."
        await save_session(session)
        logger.info("[%s] Agent ended the call: %s", session.task_id, reason or "no reason given")
        events.publish(
            session.task_id, {"type": "status", "status": "agent_ended", "reason": reason}
        )
        if on_end_call is not None:
            await on_end_call()
        return "The call is ending. Say nothing further."

    if name == "escalate_to_human":
        session.escalated = True
        session.escalation_reason = str(arguments.get("reason", "")).strip() or None
        await save_session(session)
        events.publish(
            session.task_id, {"type": "escalation", "reason": session.escalation_reason}
        )

        # Actually reach the customer. Setting a flag on a session nobody is
        # watching is a note, not an escalation - and the representative is on
        # the line right now.
        delivered = await notify.escalate(session, session.escalation_reason or "")
        if delivered:
            events.publish(
                session.task_id, {"type": "escalation_sent", "channels": delivered}
            )
            return (
                "The customer has been notified over "
                + " and ".join(delivered)
                + ". Tell the representative you need a moment, or ask for a callback number."
            )
        # Be honest with the agent rather than letting it promise a rescue that
        # is not coming.
        return (
            "No one could be reached automatically. Ask the representative for a "
            "direct callback number and a reference, then close the call politely."
        )

    logger.warning("Unknown tool call %r for task %s", name, session.task_id)
    return f"Unknown tool: {name}"
