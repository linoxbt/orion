"""A new account gets worked examples, exactly once, and they never count.

The risk here is not that seeding fails - it is that a seeded example is
mistaken for a real negotiation. A sample carrying a plausible saving that got
summed into a customer's total would be the interface asserting they kept money
they never kept.
"""

import asyncio

import pytest

from app.models import NegotiationStatus
from app.services import demo_seed


class TestSamples:
    def test_every_status_is_represented(self):
        samples = demo_seed.build_samples("user-1")
        assert len(samples) == 5
        assert {s.status for s in samples} == {
            NegotiationStatus.PENDING,
            NegotiationStatus.CALLING,
            NegotiationStatus.COMPLETED,
            NegotiationStatus.FAILED,
        }

    def test_every_sample_is_flagged(self):
        """The whole safety property depends on this one field."""
        assert all(s.is_sample for s in demo_seed.build_samples("user-1"))

    def test_samples_belong_to_the_account_they_were_seeded_for(self):
        assert all(s.user_id == "user-9" for s in demo_seed.build_samples("user-9"))

    def test_task_ids_are_unique_per_account(self):
        a = demo_seed.build_samples("user-1")
        b = demo_seed.build_samples("user-2")
        ids = [s.task_id for s in a + b]
        assert len(ids) == len(set(ids))

    def test_only_one_sample_claims_a_verified_saving(self):
        """A verified sample produces a public receipt, so there should be a
        deliberate number of them rather than an accidental five."""
        samples = demo_seed.build_samples("user-1")
        assert sum(1 for s in samples if s.verified) == 1

    def test_an_escalated_example_exists(self):
        samples = demo_seed.build_samples("user-1")
        assert any(s.escalated and s.escalation_reason for s in samples)


class TestSeedingOnce:
    def test_a_new_account_is_seeded(self, client):
        seeded = asyncio.run(demo_seed.seed_if_new("brand-new-user"))
        assert seeded == 5

        from app.store import list_sessions

        rows = asyncio.run(list_sessions("brand-new-user"))
        assert len(rows) == 5
        assert all(r.is_sample for r in rows)

    def test_an_account_that_already_has_negotiations_is_left_alone(self, client):
        """Examples appearing later, among real work, would be worse than an
        empty dashboard."""
        client.post(
            "/api/negotiations/start",
            headers={"X-Orion-Admin-Key": __import__("tests.conftest", fromlist=["ADMIN_KEY"]).ADMIN_KEY,
                     "X-Orion-User": "existing-user"},
            json={"provider": "Real", "phone_number": "+15551110000", "vertical": "cable_internet"},
        )
        assert asyncio.run(demo_seed.seed_if_new("existing-user")) == 0

    def test_seeding_is_not_repeated_on_a_second_visit(self, client):
        assert asyncio.run(demo_seed.seed_if_new("returning-user")) == 5
        assert asyncio.run(demo_seed.seed_if_new("returning-user")) == 0

        from app.store import list_sessions

        assert len(asyncio.run(list_sessions("returning-user"))) == 5

    def test_a_seeding_failure_never_blocks_the_user(self, client, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("database is down")

        monkeypatch.setattr("app.store.list_sessions", boom)
        assert asyncio.run(demo_seed.seed_if_new("unlucky-user")) == 0


class TestSeedingReachesTheDashboard:
    """The dashboard is where people land after signing in, and it lists
    negotiations without ever reading the profile. Seeding only on profile
    access left a new account staring at an empty page.
    """

    def test_the_listing_endpoint_seeds_a_new_account(self, client):
        from tests.conftest import ADMIN_KEY

        headers = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "dashboard-first"}
        rows = client.get("/api/negotiations", headers=headers).json()

        assert len(rows) == 5
        assert all(r["is_sample"] for r in rows)

    def test_a_second_load_does_not_seed_again(self, client):
        from tests.conftest import ADMIN_KEY

        headers = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "twice-loaded"}
        first = client.get("/api/negotiations", headers=headers).json()
        second = client.get("/api/negotiations", headers=headers).json()

        assert len(first) == len(second) == 5
        assert {r["task_id"] for r in first} == {r["task_id"] for r in second}

    def test_an_account_with_real_work_is_never_seeded(self, client):
        from tests.conftest import ADMIN_KEY

        headers = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "has-real-work"}
        client.post(
            "/api/negotiations/start",
            headers=headers,
            json={"provider": "Real", "phone_number": "+15551110000", "vertical": "cable_internet"},
        )
        rows = client.get("/api/negotiations", headers=headers).json()

        assert len(rows) == 1
        assert rows[0]["is_sample"] is False

    def test_samples_stay_scoped_to_their_own_account(self, client):
        from tests.conftest import ADMIN_KEY

        a = client.get(
            "/api/negotiations", headers={"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "seed-a"}
        ).json()
        b = client.get(
            "/api/negotiations", headers={"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "seed-b"}
        ).json()

        assert {r["task_id"] for r in a}.isdisjoint({r["task_id"] for r in b})
