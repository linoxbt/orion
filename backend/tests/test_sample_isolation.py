"""A worked example must never behave like a real negotiation.

The seeded samples carry genuine provider numbers - Comcast, AT&T, a hospital
billing line - and invented bills. `is_sample` existed but was read only by the
dashboard's totals, so nothing stopped a customer authorising one and putting
an agent on the phone to a real company arguing from figures nobody was billed.
"""

from datetime import date, timedelta

import pytest

from app.services import demo_seed
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}


@pytest.fixture
def sample_id(client) -> str:
    """The first seeded sample on a fresh account."""
    rows = client.get("/api/negotiations", headers=HEADERS).json()
    samples = [r for r in rows if r["is_sample"]]
    assert samples, "a new account should be seeded"
    return samples[0]["task_id"]


class TestSamplesAreNotCallable:
    def test_calling_a_sample_is_refused(self, client, sample_id):
        client.post(
            f"/api/negotiations/{sample_id}/consent",
            headers=HEADERS,
            json={"signer_name": "Denis", "agreed": True},
        )
        res = client.post(f"/api/negotiations/{sample_id}/call", headers=HEADERS)
        assert res.status_code == 409
        assert "sample_negotiation" in res.json()["detail"]

    def test_refused_even_once_authorised(self, client, sample_id):
        """Consent is the only gate that used to stand between a sample and a
        real phone call."""
        client.post(
            f"/api/negotiations/{sample_id}/consent",
            headers=HEADERS,
            json={"signer_name": "Denis", "agreed": True},
        )
        session = client.get(f"/api/negotiations/{sample_id}", headers=HEADERS).json()
        assert session["authorized"] is True

        assert client.post(
            f"/api/negotiations/{sample_id}/call", headers=HEADERS
        ).status_code == 409

    def test_a_real_negotiation_is_still_callable(self, client):
        """The guard must not block the actual product."""
        task_id = client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567",
                  "vertical": "cable_internet"},
        ).json()["task_id"]
        client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=HEADERS,
            json={"signer_name": "Denis", "agreed": True},
        )
        res = client.post(f"/api/negotiations/{task_id}/call", headers=HEADERS)
        # 503 is "Twilio unconfigured under test" - it got past the sample gate.
        assert res.status_code != 409


class TestSamplesAreNotRenewals:
    def test_a_sample_never_appears_as_a_renewal(self, client):
        """A sample carries a contract end date so the bill looks real, which
        made it surface as a genuine renewal inviting a call."""
        rows = client.get("/api/negotiations", headers=HEADERS).json()
        assert any(r["is_sample"] for r in rows)

        renewals = client.get("/api/renewals", headers=HEADERS).json()
        sample_ids = {r["task_id"] for r in rows if r["is_sample"]}
        assert not sample_ids & {r["task_id"] for r in renewals}

    def test_a_real_renewal_still_shows(self, client):
        soon = (date.today() + timedelta(days=10)).isoformat()
        client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={
                "provider": "RealCorp",
                "phone_number": "+15550001111",
                "vertical": "cable_internet",
                "bill": {"provider": "RealCorp", "contract_end_date": soon},
            },
        )
        renewals = client.get("/api/renewals", headers=HEADERS).json()
        assert any(r["provider"] == "RealCorp" for r in renewals)


class TestSeededNumbersAreReal:
    def test_the_samples_do_carry_dialable_numbers(self):
        """Pinning why the guards above exist: these are not 555 numbers."""
        numbers = {s.phone_number for s in demo_seed.build_samples("u1")}
        assert "+18009346489" in numbers  # Comcast
        assert all(not n.startswith("+1555") for n in numbers if n.startswith("+1"))
