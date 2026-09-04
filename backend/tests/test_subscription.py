"""A monthly plan that actually renews.

The first implementation charged once and granted thirty days. A paying
customer then fell back to the free tier in silence a month later, with no
renewal, no card on file and no warning. The requirement was "$15 per month".
"""

import pytest

from app.config import settings
from app.models import UserProfile
from app.services import paystack


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "paystack_secret_key", "sk_test_1")
    monkeypatch.setattr(settings, "public_app_url", "https://example.com")
    monkeypatch.setattr(settings, "paystack_plan_code", "")
    paystack._plan_code = None
    yield
    paystack._plan_code = None


def _client(monkeypatch, get=None, post=None, sent=None):
    class Response:
        def __init__(self, payload, status=200):
            self._payload = payload
            self.status_code = status

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None, params=None):
            return Response(get(url) if get else {"data": []})

        async def post(self, url, headers=None, json=None):
            if sent is not None:
                sent.setdefault(url.rsplit("/", 1)[-1], []).append(json)
            return Response(post(url, json) if post else {"data": {}})

    monkeypatch.setattr(paystack.httpx, "AsyncClient", lambda **kw: Client())


class TestPlan:
    def test_a_monthly_plan_is_created_when_none_exists(self, monkeypatch):
        import asyncio

        sent = {}
        _client(
            monkeypatch,
            get=lambda url: {"data": []},
            post=lambda url, body: {"data": {"plan_code": "PLN_new"}},
            sent=sent,
        )
        code = asyncio.run(paystack.ensure_plan(22500, "NGN"))
        assert code == "PLN_new"
        assert sent["plan"][0]["interval"] == "monthly"
        assert sent["plan"][0]["amount"] == 2250000

    def test_an_existing_plan_is_reused(self, monkeypatch):
        """Otherwise every checkout litters the merchant's dashboard."""
        import asyncio

        sent = {}
        _client(
            monkeypatch,
            get=lambda url: {
                "data": [
                    {
                        "name": paystack.PLAN_NAME,
                        "amount": 2250000,
                        "currency": "NGN",
                        "interval": "monthly",
                        "plan_code": "PLN_existing",
                    }
                ]
            },
            sent=sent,
        )
        assert asyncio.run(paystack.ensure_plan(22500, "NGN")) == "PLN_existing"
        assert "plan" not in sent

    def test_a_pinned_plan_wins(self, monkeypatch):
        import asyncio

        monkeypatch.setattr(settings, "paystack_plan_code", "PLN_pinned")
        assert asyncio.run(paystack.ensure_plan(22500, "NGN")) == "PLN_pinned"

    def test_the_checkout_is_attached_to_the_plan(self, monkeypatch):
        """Without this it is a single charge dressed up as a subscription."""
        import asyncio

        sent = {}
        _client(
            monkeypatch,
            get=lambda url: {"data": []},
            post=lambda url, body: (
                {"data": {"plan_code": "PLN_x"}}
                if url.endswith("/plan")
                else {"data": {"authorization_url": "https://pay", "reference": "T1"}}
            ),
            sent=sent,
        )
        asyncio.run(paystack.start_upgrade("user-1", "a@b.com", 22500, "NGN"))
        assert sent["initialize"][0]["plan"] == "PLN_x"

    def test_a_plan_failure_still_lets_someone_pay(self, monkeypatch):
        """A dashboard problem must not block an upgrade outright."""
        import asyncio

        sent = {}

        def blow_up(url):
            raise RuntimeError("paystack is down")

        _client(
            monkeypatch,
            get=blow_up,
            post=lambda url, body: {"data": {"authorization_url": "https://pay", "reference": "T1"}},
            sent=sent,
        )
        out = asyncio.run(paystack.start_upgrade("user-1", "a@b.com", 22500, "NGN"))
        assert out["authorization_url"] == "https://pay"
        assert "plan" not in sent["initialize"][0]


class TestRenewalExtendsThePlan:
    def test_each_new_charge_pushes_the_expiry_out(self, monkeypatch):
        """Paystack charges monthly on its own; every one must extend."""
        import asyncio
        from datetime import datetime, timezone

        from app.routers import billing_plan

        saved = {"p": UserProfile(id="user-1")}

        async def get_profile(uid):
            return saved["p"]

        async def upsert(profile):
            saved["p"] = profile
            return profile

        monkeypatch.setattr(billing_plan.supabase_store, "get_profile", get_profile)
        monkeypatch.setattr(billing_plan.supabase_store, "upsert_profile", upsert)

        asyncio.run(billing_plan._grant_pro("user-1", "ref-1", subscription_code="SUB_1"))
        first = saved["p"].plan_expires_at
        assert saved["p"].plan == "pro"
        assert saved["p"].subscription_code == "SUB_1"

        # The same payment must not extend it twice.
        asyncio.run(billing_plan._grant_pro("user-1", "ref-1"))
        assert saved["p"].plan_expires_at == first

        # A new month's charge must.
        asyncio.run(billing_plan._grant_pro("user-1", "ref-2"))
        assert saved["p"].plan_expires_at > first
        assert datetime.fromisoformat(saved["p"].plan_expires_at) > datetime.now(timezone.utc)

    def test_cancelling_does_not_revoke_the_month_already_paid_for(self, monkeypatch):
        import asyncio

        from app.routers import billing_plan

        saved = {"p": UserProfile(id="user-1", plan="pro", plan_expires_at="2099-01-01T00:00:00+00:00")}

        async def get_profile(uid):
            return saved["p"]

        async def upsert(profile):
            saved["p"] = profile
            return profile

        monkeypatch.setattr(billing_plan.supabase_store, "get_profile", get_profile)
        monkeypatch.setattr(billing_plan.supabase_store, "upsert_profile", upsert)

        asyncio.run(billing_plan._mark_subscription("user-1", "non-renewing"))
        assert saved["p"].plan == "pro"
        assert saved["p"].subscription_status == "non-renewing"
