from functools import lru_cache

import stripe

from app.config import settings
from app.models import NegotiationSession

DEFAULT_SUCCESS_FEE_RATE = 0.25  # build spec Section 11: ~25% of first-year annualized savings


class StripeNotConfigured(RuntimeError):
    pass


@lru_cache
def get_client() -> stripe.StripeClient:
    if not settings.stripe_secret_key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    return stripe.StripeClient(settings.stripe_secret_key)


def charge_success_fee(
    session: NegotiationSession, monthly_savings: float, fee_rate: float = DEFAULT_SUCCESS_FEE_RATE
) -> stripe.PaymentIntent:
    """Charges a percentage of first-year annualized savings (build spec
    Section 11). Caller is responsible for having already verified the outcome
    (see NegotiationSession.verified) before calling this.
    """
    client = get_client()
    annualized_savings = monthly_savings * 12
    fee_amount_cents = round(annualized_savings * fee_rate * 100)
    return client.v1.payment_intents.create({
        "amount": fee_amount_cents,
        "currency": "usd",
        "automatic_payment_methods": {"enabled": True},
        "metadata": {
            "task_id": session.task_id,
            "provider": session.provider,
            "monthly_savings": str(monthly_savings),
            "fee_rate": str(fee_rate),
        },
    })
