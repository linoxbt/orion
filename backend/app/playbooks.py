"""Per-vertical and per-provider negotiation playbooks (build spec Section 7).

Two layers:
  - Generic, vertical-level entries (provider=None) - broad, publicly-known
    retention-call tactics that apply regardless of which company is on the
    other end of the line. These are the original 3 entries and remain the
    fallback when a call's provider doesn't match a specific playbook below.
  - Provider-specific entries for the handful of major US telecom/cable
    brands the Phase 1 MVP scope actually covers (build spec Section 4:
    cable/internet/cell only - medical billing is Phase 2, and unlike
    telecom isn't dominated by a small brand set, so it stays generic-only).

Provider-specific content here is the same kind of thing already
well-documented across consumer forums (Reddit r/personalfinance,
r/Verizon, DoNotPay-style retention-call guides, etc.) - which department
tends to have discount authority, what kind of phrasing commonly triggers
a transfer to that department, what categories of leverage tend to work.
It is deliberately NOT exact discount percentages or offer tables, which
change constantly, aren't publicly published, and would be fabricated if
stated as fact here. Real verified per-provider discount data still needs
the content-research pipeline described in build spec Section 4 Phase 2.
"""

import re

from pydantic import BaseModel


class Playbook(BaseModel):
    vertical: str
    provider: str | None = None
    display_name: str
    strategy_notes: str
    trigger_phrases: list[str] = []
    retention_routing: str | None = None


_GENERIC_PLAYBOOKS: dict[str, Playbook] = {
    "cable_internet": Playbook(
        vertical="cable_internet",
        display_name="Cable / Internet",
        strategy_notes=(
            "Ask for the retention or loyalty department by name if the first "
            "rep can't authorize a discount. Mention how long you've been a "
            "customer and that you're comparing prices from other providers in "
            "the area. Don't accept the first offer - ask 'is that the best you "
            "can do' before agreeing, and ask about any promotional pricing not "
            "advertised on the website."
        ),
    ),
    "cell_phone": Playbook(
        vertical="cell_phone",
        display_name="Cell Phone / Wireless",
        strategy_notes=(
            "Mention you're considering switching carriers - this often routes "
            "the call to a retention team with more discount authority than "
            "general customer service. Ask about loyalty discounts, autopay "
            "discounts, and any promotional plans not advertised publicly."
        ),
    ),
    "medical": Playbook(
        vertical="medical",
        display_name="Medical Billing",
        strategy_notes=(
            "Ask whether a prompt-pay discount, financial hardship program, or "
            "charity care policy applies. Request an itemized bill and ask "
            "about the cash/self-pay rate, which is often lower than the "
            "billed insurance rate. Don't agree to a payment plan on the call "
            "without confirming the total amount first."
        ),
    ),
}

_PROVIDER_PLAYBOOKS: dict[tuple[str, str], Playbook] = {
    ("cable_internet", "comcast"): Playbook(
        vertical="cable_internet",
        provider="comcast",
        display_name="Comcast / Xfinity",
        strategy_notes=(
            "Xfinity's front-line reps have limited discount authority; ask "
            "directly for the 'Customer Loyalty' or 'Retention' team, or say "
            "you're calling to 'cancel or downgrade service' to route there "
            "faster than asking generically for a discount. Retention reps can "
            "typically apply an existing promotional rate (usually a 12-month "
            "term) without needing supervisor sign-off. Xfinity Mobile line "
            "bundling is a common retention offer if the account doesn't "
            "already have it."
        ),
        trigger_phrases=[
            "I'm calling to cancel or downgrade my service",
            "I'd like to speak with the customer loyalty department",
            "I'm comparing pricing with [named local competitor, e.g. AT&T Fiber or T-Mobile Home Internet]",
        ],
        retention_routing="Ask for Customer Loyalty / Retention; saying 'cancel' in the phone menu often routes there directly.",
    ),
    ("cable_internet", "spectrum"): Playbook(
        vertical="cable_internet",
        provider="spectrum",
        display_name="Spectrum / Charter",
        strategy_notes=(
            "Spectrum doesn't lock customers into contracts, so the usual "
            "'I'm stuck in a contract' leverage doesn't apply - lead instead "
            "with a specific competitor's advertised price in the area. "
            "Spectrum's retention team is generally less flexible than "
            "Xfinity's, so set realistic expectations, but a 'Retention "
            "Specialist' transfer is still commonly reported as effective. "
            "Ask about any promotional or loyalty-tier pricing not shown at "
            "signup."
        ),
        trigger_phrases=[
            "I'd like to be transferred to a retention specialist",
            "I'm looking to cancel or downgrade my plan",
            "[Named competitor] is offering a lower rate for similar speeds in my area",
        ],
        retention_routing="Ask specifically for a 'Retention Specialist' - general support reps often can't apply discounts themselves.",
    ),
    ("cable_internet", "cox"): Playbook(
        vertical="cable_internet",
        provider="cox",
        display_name="Cox Communications",
        strategy_notes=(
            "Ask for the 'Customer Retention' department. Cox's no-contract "
            "'StraightUp Internet' tier is sometimes useful leverage even if "
            "you don't intend to switch to it - mentioning it signals you've "
            "done pricing research. As with the other cable providers, "
            "naming a specific regional competitor's advertised rate tends to "
            "get a better response than a vague 'can you do better.'"
        ),
        trigger_phrases=[
            "I'd like to speak with customer retention",
            "I'm considering switching to a lower-cost plan or a different provider",
        ],
        retention_routing="Ask for Customer Retention directly; front-line billing support has limited discount authority.",
    ),
    ("cell_phone", "verizon"): Playbook(
        vertical="cell_phone",
        provider="verizon",
        display_name="Verizon",
        strategy_notes=(
            "Selecting 'cancel service' in Verizon's phone menu commonly "
            "routes to the retention team faster than the general billing "
            "queue. Check whether autopay and paperless-billing discounts "
            "are actually applied - these are sometimes missed and are close "
            "to automatic once flagged. Multi-line accounts should confirm "
            "every eligible discount is applied per line, not just the "
            "account total."
        ),
        trigger_phrases=[
            "I'm calling about canceling my service",
            "I'm comparing plans with T-Mobile and AT&T",
            "Can you confirm my autopay and paperless billing discounts are applied to every line",
        ],
        retention_routing="Select 'cancel service' in the IVR, or explicitly ask for the retention/loyalty team.",
    ),
    ("cell_phone", "att"): Playbook(
        vertical="cell_phone",
        provider="att",
        display_name="AT&T",
        strategy_notes=(
            "Ask for AT&T's 'Loyalty' department by name. AT&T has been "
            "reported to offer temporary 'loyalty credits' applied over a "
            "fixed number of months rather than a permanent plan-price "
            "change - confirm which one you're being offered and for how "
            "long before agreeing. As with Verizon, naming specific "
            "competitor pricing (T-Mobile, Verizon) is a common and "
            "effective trigger."
        ),
        trigger_phrases=[
            "I'd like to speak with the loyalty department",
            "I'm considering switching to Verizon or T-Mobile",
        ],
        retention_routing="Ask for the Loyalty department specifically - front-line support usually can't apply retention credits.",
    ),
    ("cell_phone", "tmobile"): Playbook(
        vertical="cell_phone",
        provider="tmobile",
        display_name="T-Mobile",
        strategy_notes=(
            "T-Mobile reps are commonly reported to have somewhat more "
            "on-the-spot discretion than Verizon/AT&T front-line staff, but "
            "a retention/loyalty transfer is still the more reliable path "
            "for anything beyond a small adjustment. Ask specifically about "
            "any promotional plans not listed on the public website and "
            "about price-lock guarantees, which T-Mobile has marketed "
            "heavily and can be useful leverage if the account isn't on one."
        ),
        trigger_phrases=[
            "I'd like to speak with retention about my plan",
            "Are there any current promotions not listed on the website",
            "I'm comparing pricing with Verizon and AT&T",
        ],
        retention_routing="Ask for the retention/loyalty team if the first rep can't adjust pricing directly.",
    ),
}

_PROVIDER_ALIASES: dict[str, list[str]] = {
    "comcast": ["comcast", "xfinity"],
    "spectrum": ["spectrum", "charter"],
    "cox": ["cox"],
    "verizon": ["verizon"],
    "att": ["at&t", "att"],
    "tmobile": ["t-mobile", "tmobile", "t mobile"],
}


def _normalize(text: str) -> str:
    """Lowercase and strip everything but letters/digits, so 'AT&T',
    'at&t', and 'At T' all normalize identically for alias matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _match_provider(vertical: str, provider: str | None) -> Playbook | None:
    if not provider:
        return None
    normalized = _normalize(provider)
    for canonical, aliases in _PROVIDER_ALIASES.items():
        normalized_aliases = (_normalize(alias) for alias in aliases)
        if any(alias in normalized or normalized in alias for alias in normalized_aliases):
            return _PROVIDER_PLAYBOOKS.get((vertical, canonical))
    return None


def get_playbook(vertical: str, provider: str | None = None) -> Playbook | None:
    """Provider-specific playbook if one exists and matches, else the
    vertical's generic fallback, else None."""
    specific = _match_provider(vertical, provider)
    if specific is not None:
        return specific
    return _GENERIC_PLAYBOOKS.get(vertical)


def list_playbooks() -> list[Playbook]:
    return [*_GENERIC_PLAYBOOKS.values(), *_PROVIDER_PLAYBOOKS.values()]
