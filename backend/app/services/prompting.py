"""The negotiation prompt and its keyterms, shared by both voice backends.

Lifted out of the old Gemini Live bridge unchanged in substance: the same
system instruction now drives the Voice Agent API's session.system_prompt and
the stt_gemini turn loop's system message, so the two backends are actually
comparable on a call rather than differing by prompt as well as pipeline.
"""

from app.models import NegotiationSession
from app.playbooks import get_playbook
from app.services.account_vault import FIELD_LABELS, available_fields
from app.services.languages import instruction_for


def prompting_fields(session: NegotiationSession) -> list[str]:
    """Which verification fields this call can answer for.

    Only the field NAMES ever reach the prompt - the values stay sealed and are
    fetched one at a time by the provide_verification tool, so a model can't
    volunteer a security PIN it was never asked for.
    """
    return available_fields(session.account_details)

# Keyterms bias transcription toward words the model would otherwise mangle -
# provider brands, and the retention-department vocabulary a negotiation call
# turns on. Realtime caps this at 100 terms.
KEYTERM_LIMIT = 100

_BASE_KEYTERMS = [
    "retention department",
    "loyalty department",
    "promotional rate",
    "confirmation number",
    "account number",
    "autopay discount",
    "price lock",
    "early termination fee",
]


# What the call is for. Orion is not only a bill-reduction agent: a receipt for
# a faulty purchase wants a refund, a duplicated charge wants disputing, and
# asking a marketplace to "lower the monthly rate" on a one-off order would be
# nonsense. The document decides which of these the call is.
OBJECTIVES: dict[str, str] = {
    "reduce_recurring_rate": (
        "get their ongoing monthly rate reduced. Don't accept the first offer: push "
        "through at least two or three rounds before settling, the way a skilled human "
        "negotiator would"
    ),
    "waive_fees": (
        "get specific charges removed from the bill. Name each fee individually - fees "
        "and equipment rental are often waived even when the base rate won't move"
    ),
    "request_refund": (
        "obtain a refund for this purchase. Establish what was wrong with it, ask "
        "plainly for money back rather than credit, and get a reference number"
    ),
    "dispute_charge": (
        "dispute a charge that looks wrong. State exactly which charge and why, ask for "
        "it to be reversed, and get a reference number for the dispute"
    ),
    "cancel_service": (
        "cancel this service cleanly. Confirm the final billing date, that no early "
        "termination fee applies, and get a cancellation reference. If they offer a "
        "retention discount, log it and ask the customer's representative-of-record "
        "rules aside - report it rather than accepting on their behalf"
    ),
    "payment_plan": (
        "arrange an affordable payment plan or hardship arrangement on this balance. "
        "Ask about financial hardship programmes and any charity-care or discount "
        "policy before agreeing to a figure"
    ),
    "request_itemisation": (
        "get a full itemised breakdown of this bill. You cannot argue a charge you "
        "cannot see, so get the detail first and log what you're told"
    ),
    "none": "understand what this charge is and report back, without committing to anything",
}


def system_instruction(session: NegotiationSession) -> str:
    objective_key = (session.bill.call_objective if session.bill else None) or "reduce_recurring_rate"
    objective = OBJECTIVES.get(objective_key, OBJECTIVES["reduce_recurring_rate"])

    base = (
        "You are Orion, an AI representative placing an outbound phone call on "
        f"behalf of a customer, to {session.provider}. Your goal on this call is to "
        f"{objective}. "
        "Identify yourself as an AI representative at the start of the call - "
        "never claim to be the account holder or a human, and never misrepresent "
        "facts about the customer's account or their purchase."
    )

    if session.bill is not None and session.bill.objective_summary:
        base += f" Specifically: {session.bill.objective_summary}"

    # A model handed an English system prompt answers in English however well
    # it understood the question, so the language has to be stated.
    base += instruction_for(session.language)
    playbook = get_playbook(session.vertical, session.provider)
    if playbook is not None:
        label = "Provider-specific" if playbook.provider else "Vertical-specific"
        base += f" {label} guidance: {playbook.strategy_notes}"
        if playbook.retention_routing:
            base += f" Retention routing: {playbook.retention_routing}"
        if playbook.trigger_phrases:
            phrases = "; ".join(playbook.trigger_phrases)
            base += f" Phrases that commonly help move the call forward: {phrases}."

    base += (
        " Call log_offer every time the representative names a concrete price or "
        "offer, whether or not you accept it. When you have agreed a new rate, "
        "ask for a confirmation number and call record_confirmation_number with "
        "it - without that the saving can't be verified and the customer isn't "
        "billed."
    )

    bill = session.bill
    if bill is not None:
        facts: list[str] = []
        symbol = bill.currency or ""
        if bill.current_rate is not None:
            facts.append(f"they currently pay {symbol}{bill.current_rate:.2f} a month")
        if bill.amount_due is not None:
            facts.append(f"this statement is {symbol}{bill.amount_due:.2f}")
        if bill.plan_details:
            facts.append(f"the plan is {bill.plan_details}")
        if bill.billing_period:
            facts.append(f"the billing period is {bill.billing_period}")
        if bill.contract_end_date:
            facts.append(f"the contract or promotional period ends {bill.contract_end_date}")
        if bill.customer_since:
            facts.append(f"they have been a customer since {bill.customer_since}")

        if facts:
            base += " You have the customer's actual bill in front of you: " + "; ".join(facts) + "."

        # The itemisation is where the winnable money usually is - a rep who
        # won't move the base rate will often drop an equipment fee.
        charges = [
            f"{item.description}"
            + (f" at {symbol}{item.amount:.2f}" if item.amount is not None else "")
            for item in bill.line_items[:12]
        ]
        if charges:
            base += (
                " The bill itemises: " + "; ".join(charges) + ". Fees and equipment rental are "
                "often waived even when the base rate won't move, so name them specifically."
            )

        if bill.notes:
            base += f" Worth knowing: {bill.notes}"

        base += (
            " Quote these figures accurately - never invent a number, and if the "
            "representative's figures differ from the bill, ask them to explain the "
            "difference rather than assuming the bill is wrong."
        )

    # A real provider line answers with a menu, not a person.
    base += (
        " This is a real company's phone line, so expect an automated menu first. "
        "Listen to the whole menu before doing anything, then call press_keys with "
        "the option you want - billing, account services, or cancellations, since "
        "cancellations usually routes to the team with discount authority. If a "
        "menu asks you to say why you are calling, just say it. If you get stuck "
        "in a menu loop, press 0 or say 'representative', which reaches an "
        "operator on most systems."
    )

    # Hold music is not a conversation partner.
    base += (
        " While you are on hold, say nothing at all. Hold music and recorded "
        "messages are not people; do not respond to them, and wait until a human "
        "actually greets you before speaking."
    )

    fields = prompting_fields(session)
    if fields:
        readable = ", ".join(FIELD_LABELS[field] for field in fields)
        base += (
            " The representative will ask you to verify the account before "
            f"discussing it. You can provide {readable} - call provide_verification "
            "with the specific field asked for, one at a time, and read back only "
            "what it returns. Never volunteer these details, never guess one that "
            "isn't on file, and never read out a detail you were not asked for."
        )
    else:
        base += (
            " You have no account verification details on file. If the "
            "representative asks you to verify the account, say you don't have "
            "that detail to hand and call escalate_to_human."
        )

    base += (
        " If the representative refuses outright, becomes hostile, or demands "
        "something you genuinely cannot provide, call escalate_to_human rather "
        "than continuing to push."
    )

    # Nobody else is going to hang up. The customer is not on this call, and
    # the line stays open - and billing - until this side ends it.
    base += (
        " You are responsible for ending the call. When the conversation is "
        "genuinely finished - the change is agreed and read back, or you have "
        "been refused and have nothing left to ask - thank them, say goodbye, "
        "and then call end_call with one sentence saying how it ended. Do not "
        "stay silently on an open line, and do not end a call you could still "
        "push on."
    )
    return base


def greeting(session: NegotiationSession) -> str:
    """Orion speaks first - the person answering has no idea why they were called."""
    return (
        f"Hi, this is Orion, an AI assistant calling on behalf of a {session.provider} "
        "customer about their account. This call is recorded. I'm hoping to talk "
        "through some options for lowering their monthly bill - could you help with "
        "that, or should I ask for the retention team?"
    )


def keyterms(session: NegotiationSession) -> list[str]:
    terms = [session.provider, *_BASE_KEYTERMS]
    playbook = get_playbook(session.vertical, session.provider)
    if playbook is not None:
        terms.extend(playbook.trigger_phrases)
        terms.append(playbook.display_name)

    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        cleaned = term.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique.append(cleaned)
    return unique[:KEYTERM_LIMIT]
