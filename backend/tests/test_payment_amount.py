"""A payment has to be for the thing it claims to buy.

Paystack's inline checkout runs on the public key, where both the amount and
the metadata are the caller's to choose. The webhook is signed, so only
Paystack can deliver it - but Paystack will happily sign a charge for fifty
naira with somebody's user id attached, and that used to buy a month of
unlimited bills.
"""

import pytest

from app.config import settings
from app.routers.billing_plan import _covers_the_plan


@pytest.fixture(autouse=True)
def _plan(monkeypatch):
    monkeypatch.setattr(settings, "pro_price", 750)
    monkeypatch.setattr(settings, "paystack_currency", "NGN")


class TestWhatCountsAsPayingForPro:
    def test_the_plan_price_is_accepted(self):
        assert _covers_the_plan({"amount": 75000, "currency": "NGN"}) is True

    def test_more_than_the_plan_price_is_accepted(self):
        assert _covers_the_plan({"amount": 90000, "currency": "NGN"}) is True

    def test_a_token_payment_is_refused(self):
        assert _covers_the_plan({"amount": 5000, "currency": "NGN"}) is False

    def test_a_free_charge_is_refused(self):
        assert _covers_the_plan({"amount": 0, "currency": "NGN"}) is False

    def test_another_currency_is_refused_rather_than_converted(self):
        """750 USD-cents is not 750 naira, and this is not the place to guess
        an exchange rate."""
        assert _covers_the_plan({"amount": 75000, "currency": "USD"}) is False

    def test_a_missing_amount_is_refused(self):
        assert _covers_the_plan({"currency": "NGN"}) is False
        assert _covers_the_plan({}) is False

    def test_a_nonsense_amount_is_refused(self):
        assert _covers_the_plan({"amount": "lots", "currency": "NGN"}) is False

    def test_a_charge_with_no_currency_is_judged_on_amount_alone(self):
        """Older Paystack payloads omit it; the amount is still in the
        merchant's own currency."""
        assert _covers_the_plan({"amount": 75000}) is True
