"""The free allowance, and how an account gets off it.

Two properties matter more than the rest: an allowance that comes back on its
own when the month turns, and an upgrade that no browser can grant itself.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserProfile
from app.services import paystack, quota


def _profile(**kw) -> UserProfile:
    return UserProfile(id="user-1", **kw)


class TestAllowance:
    def test_a_fresh_account_has_the_full_allowance(self):
        state = quota.describe(_profile())
        assert state["plan"] == "free"
        assert state["remaining"] == quota.FREE_MONTHLY_BILLS

    def test_usage_counts_down(self):
        state = quota.describe(_profile(bills_used=2, quota_month=quota.current_month()))
        assert state["used"] == 2
        assert state["remaining"] == quota.FREE_MONTHLY_BILLS - 2

    def test_a_count_from_another_month_is_stale(self):
        """The reset needs nothing to run on the first of the month."""
        state = quota.describe(_profile(bills_used=5, quota_month="2020-01"))
        assert state["used"] == 0
        assert state["remaining"] == quota.FREE_MONTHLY_BILLS

    def test_remaining_never_goes_negative(self):
        state = quota.describe(_profile(bills_used=99, quota_month=quota.current_month()))
        assert state["remaining"] == 0


class TestPaidPlan:
    def test_a_paid_plan_is_unlimited(self):
        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        state = quota.describe(_profile(plan="pro", plan_expires_at=future, bills_used=99))
        assert state["unlimited"] is True
        assert state["limit"] is None
        assert state["remaining"] is None

    def test_a_lapsed_plan_is_free_again(self):
        """No sweep job: an expiry in the past is simply not live."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        state = quota.describe(_profile(plan="pro", plan_expires_at=past))
        assert state["plan"] == "free"
        assert state["remaining"] == quota.FREE_MONTHLY_BILLS

    def test_a_paid_plan_with_no_expiry_is_live(self):
        assert quota.describe(_profile(plan="pro"))["unlimited"] is True

    def test_an_unparseable_expiry_does_not_lock_a_payer_out(self):
        """Wrongly downgrading someone who paid is worse than the reverse."""
        assert quota.describe(_profile(plan="pro", plan_expires_at="not a date"))["unlimited"] is True


class TestConsumption:
    @pytest.fixture
    def store(self, monkeypatch):
        saved: dict[str, UserProfile] = {}

        async def get_profile(user_id):
            return saved.get(user_id)

        async def upsert_profile(profile):
            saved[profile.id] = profile
            return profile

        monkeypatch.setattr(quota.supabase_store, "is_configured", lambda: True)
        monkeypatch.setattr(quota.supabase_store, "get_profile", get_profile)
        monkeypatch.setattr(quota.supabase_store, "upsert_profile", upsert_profile)
        return saved

    def test_the_allowance_runs_out(self, store):
        import asyncio
        from fastapi import HTTPException

        for _ in range(quota.FREE_MONTHLY_BILLS):
            asyncio.run(quota.consume_bill("user-1"))

        with pytest.raises(HTTPException) as caught:
            asyncio.run(quota.consume_bill("user-1"))
        assert caught.value.status_code == 402
        assert "free_limit_reached" in caught.value.detail

    def test_a_paid_account_is_never_refused(self, store):
        import asyncio

        store["user-1"] = UserProfile(id="user-1", plan="pro")
        for _ in range(quota.FREE_MONTHLY_BILLS * 3):
            asyncio.run(quota.consume_bill("user-1"))
        assert store["user-1"].plan == "pro"

    def test_without_a_store_nothing_is_metered_rather_than_refused(self, monkeypatch):
        import asyncio

        monkeypatch.setattr(quota.supabase_store, "is_configured", lambda: False)
        asyncio.run(quota.consume_bill("user-1"))  # must not raise


class TestWebhookSignature:
    """The webhook is the only thing that upgrades an account, so its signature
    is the only thing standing between a stranger and a free subscription."""

    def test_a_correctly_signed_body_is_accepted(self, monkeypatch):
        import hashlib
        import hmac

        from app.config import settings

        monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_123")
        body = b'{"event":"charge.success"}'
        sig = hmac.new(b"sk_test_123", body, hashlib.sha512).hexdigest()
        assert paystack.signature_is_valid(body, sig) is True

    def test_a_forged_signature_is_refused(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_123")
        assert paystack.signature_is_valid(b'{"event":"charge.success"}', "0" * 128) is False

    def test_a_body_tampered_after_signing_is_refused(self, monkeypatch):
        import hashlib
        import hmac

        from app.config import settings

        monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_123")
        sig = hmac.new(b"sk_test_123", b'{"amount":100}', hashlib.sha512).hexdigest()
        assert paystack.signature_is_valid(b'{"amount":999999}', sig) is False

    def test_an_unconfigured_deployment_verifies_nothing_and_accepts_nothing(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "paystack_secret_key", "")
        assert paystack.signature_is_valid(b"{}", "anything") is False

    def test_a_missing_signature_is_refused(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_123")
        assert paystack.signature_is_valid(b"{}", None) is False
