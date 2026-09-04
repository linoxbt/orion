from enum import Enum

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Who the customer is, so they stop retyping it into every negotiation.

    Keyed by the Dynamic user id (the JWT's `sub`), because identity comes from
    Dynamic rather than Supabase Auth.
    """

    id: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None

    phone: str | None = None
    country: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None

    preferred_language: str = "en"

    # Where to reach this person when a call stalls and needs them. Per user,
    # not per deployment: everyone using Orion has their own number and inbox,
    # and a single global escalation address would page one person about every
    # customer's call.
    escalation_whatsapp: str | None = None
    escalation_email: str | None = None

    # Plan and the free tier's monthly allowance. The month is stored next to
    # the count so the reset is a comparison rather than a scheduled job: a
    # stored month that is not the current one means the count is stale.
    plan: str = "free"
    bills_used: int = 0
    quota_month: str | None = None
    plan_expires_at: str | None = None
    payment_reference: str | None = None

    # The Paystack subscription behind a paid plan. Without these a paid
    # account was a one-off thirty-day grant that lapsed in silence.
    subscription_code: str | None = None
    subscription_status: str | None = None
    next_payment_at: str | None = None

    created_at: str | None = None
    updated_at: str | None = None

    def postal_address(self) -> str | None:
        """The address as a rep would want it read out, or None if too thin to
        be worth offering as a verification answer."""
        parts = [self.address_line1, self.address_line2, self.city, self.region, self.postal_code]
        joined = ", ".join(part.strip() for part in parts if part and part.strip())
        return joined or None


class LineItem(BaseModel):
    """One charge on the bill. The itemisation is where negotiable money hides -
    equipment rental, broadcast TV fees and regional sports fees are routinely
    waived by retention when the base rate won't move."""

    description: str = Field(description="What the charge is for, verbatim from the bill")
    amount: float | None = Field(default=None, description="The charge in the bill's currency")


class BillExtraction(BaseModel):
    """Everything worth knowing from an uploaded bill.

    Read generously: a field left blank costs the agent an argument it could
    have made on the call, so anything legible on the document belongs here.
    """

    provider: str = Field(description="The company that issued the bill, e.g. Comcast, Verizon")

    # Is this even a bill Orion can negotiate? A shop receipt has a merchant
    # name and a total but nothing recurring to argue about, and saying so is
    # far more useful than returning a row of blanks.
    document_type: str = Field(
        default="unknown",
        description=(
            "What the document actually is: 'recurring_bill' for a utility, telecom, "
            "internet or subscription statement; 'medical_bill'; 'retail_receipt' for a "
            "one-off purchase; 'other' for anything else."
        ),
    )
    is_negotiable: bool = Field(
        default=False,
        description=(
            "True only for a recurring service bill or a medical bill - the kinds a "
            "retention or billing department can actually reduce."
        ),
    )

    # Orion is not only a bill-reduction agent. A receipt for a faulty purchase
    # wants a refund; a subscription wants cancelling; a duplicate charge wants
    # disputing. Reading the document tells you which call to make, and calling
    # a merchant to "negotiate a lower rate" on a one-off purchase would be
    # nonsense.
    call_objective: str = Field(
        default="reduce_recurring_rate",
        description=(
            "What a call about this document should try to achieve. One of: "
            "'reduce_recurring_rate' (lower an ongoing bill), 'waive_fees' (remove "
            "specific charges), 'request_refund' (money back on a purchase), "
            "'dispute_charge' (a charge that looks wrong or duplicated), "
            "'cancel_service' (end a subscription or contract), 'payment_plan' "
            "(spread a large balance), 'request_itemisation' (an unclear bill that "
            "needs breaking down first), or 'none' if nothing useful can be asked for."
        ),
    )
    objective_summary: str | None = Field(
        default=None,
        description=(
            "One plain sentence naming what to ask for and why this document justifies "
            "it, e.g. 'Ask for the $27 broadcast TV fee to be waived, since it was "
            "added after the promotional period started.'"
        ),
    )
    merchant_type: str | None = Field(
        default=None,
        description="What kind of business issued this, e.g. cable provider, marketplace, hospital",
    )

    account_number: str | None = Field(default=None, description="The account number on the bill")
    account_holder_name: str | None = Field(default=None, description="The name the account is in")
    service_address: str | None = Field(default=None, description="The service or billing address")

    current_rate: float | None = Field(
        default=None, description="The recurring monthly charge in the bill's currency"
    )
    amount_due: float | None = Field(default=None, description="The total due on this statement")
    currency: str | None = Field(default=None, description="ISO currency code, e.g. USD, NGN, GBP")

    due_date: str | None = Field(default=None, description="The bill's due date, ISO 8601 if present")
    statement_date: str | None = Field(default=None, description="The statement date, ISO 8601")
    billing_period: str | None = Field(default=None, description="The period this bill covers")

    plan_details: str | None = Field(default=None, description="The plan or service tier by name")
    line_items: list[LineItem] = Field(
        default_factory=list, description="Every itemised charge, in the order shown"
    )
    contract_end_date: str | None = Field(
        default=None,
        description="When any contract or promotional period ends - real leverage on a call",
    )
    customer_since: str | None = Field(
        default=None, description="How long they've been a customer, if stated - retention leverage"
    )
    support_phone: str | None = Field(
        default=None, description="Any customer service or billing phone number printed on the bill"
    )
    notes: str | None = Field(
        default=None,
        description="Anything else a negotiator would want: late fees, promo expiry, price rises",
    )


class Offer(BaseModel):
    """One concrete offer the rep put on the table, logged by the agent's
    log_offer tool mid-call rather than reconstructed from the transcript
    afterwards - the agent knows what it just heard accepted or refused.
    """

    monthly_rate: float | None = None
    description: str = ""
    accepted: bool = False


class NegotiationStatus(str, Enum):
    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"


class NegotiationSession(BaseModel):
    task_id: str

    # Who this belongs to. Nullable so sessions created before user scoping
    # existed still load rather than being orphaned - but every new one is
    # owned, and the listing endpoint filters on it. Without this, every
    # signed-in user could list every negotiation in the system.
    user_id: str | None = None

    provider: str
    phone_number: str
    vertical: str = "cable_internet"

    # The language the call is held in. Universal-3.5 Pro transcribes 18
    # languages natively and code-switches between them without configuration,
    # so this mainly picks the agent's voice and tells it what to speak.
    language: str = "en"

    status: NegotiationStatus = NegotiationStatus.PENDING
    call_sid: str | None = None

    # A worked example seeded on a new account so the dashboard has something
    # to show. Flagged rather than silently indistinguishable: an unmarked
    # fake saving would inflate the totals and read as money someone actually
    # kept. The UI badges these and leaves them out of every sum.
    is_sample: bool = False

    # Verification (build spec Section 9) - MVP is the "human review queue"
    # tier: whoever ran/listened to the call records the outcome manually via
    # POST /api/negotiations/{task_id}/complete rather than automated parsing
    # of a confirmation email/next-bill cross-check.
    outcome: str | None = None
    confirmation_number: str | None = None
    previous_rate: float | None = None
    new_rate: float | None = None
    verified: bool = False

    # Which voice backend held this call (settings.voice_backend at the time
    # the bridge opened) - recorded per session so a run of calls can be
    # compared across backends after the fact.
    voice_backend: str | None = None

    # Offers logged mid-call by the agent's log_offer tool.
    offers: list[Offer] = []

    # Set when the agent gave up and called escalate_to_human - the call
    # reached a wall a human needs to take over (build spec Section 4 Phase 2).
    escalated: bool = False
    escalation_reason: str | None = None

    # The extracted bill this negotiation is about. Without it the agent walks
    # into the call knowing only a provider name; with it, it can quote the
    # customer's actual rate, name the line items worth waiving, and cite when
    # a promotional period ends.
    bill: BillExtraction | None = None

    # Encrypted account-verification details (app/services/account_vault.py) -
    # what a retention rep asks for before discussing the account. Sealed with
    # Fernet, never returned by the read APIs, and readable on a call only one
    # field at a time through the provide_verification tool.
    account_details: str | None = None

    # Post-call verification (app/services/verification.py): the Twilio
    # recording, its AssemblyAI transcript, and whether the outcome above was
    # extracted automatically or typed in by a human.
    recording_url: str | None = None
    # Our own copy of the recording, in private storage keyed by owner and
    # negotiation. The Twilio URL above needs account credentials the browser
    # must never hold, and Twilio drops recordings when an account lapses.
    recording_path: str | None = None
    transcript_id: str | None = None
    verification_source: str | None = None

    # Billing (build spec Section 5/11)
    fee_amount_cents: int | None = None
    stripe_payment_intent_id: str | None = None

    # Consent to act as the customer's representative and to record the call,
    # collected before a call is placed. What someone agreed to has to be
    # reconstructable later, so the wording's version and the moment of
    # agreement are recorded alongside the name they typed - "they clicked a
    # box" is not a record of anything.
    authorized: bool = False
    consent_signer_name: str | None = None
    consent_version: str | None = None
    consent_at: str | None = None
