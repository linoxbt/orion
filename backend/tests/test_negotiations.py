import asyncio

from app.store import get_session, save_session
from tests.conftest import ADMIN_HEADERS


def start(client, provider="Comcast", phone="+15551234567", vertical="cable_internet"):
    return client.post(
        "/api/negotiations/start",
        headers=ADMIN_HEADERS,
        json={"provider": provider, "phone_number": phone, "vertical": vertical},
    )


def _seed_session(client) -> str:
    res = start(client)
    return res.json()["task_id"]


def _authorize(task_id: str) -> None:
    """Flips session.authorized directly via the store, bypassing the real
    DocuSign flow (not configured in tests) - isolates the /call endpoint's
    authorization gate from DocuSign's own configuration state."""
    session = asyncio.run(get_session(task_id))
    session.authorized = True
    asyncio.run(save_session(session))


def test_start_requires_admin_key(client):
    res = client.post(
        "/api/negotiations/start",
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "unauthorized"


def test_start_rejects_wrong_admin_key(client):
    res = client.post(
        "/api/negotiations/start",
        headers={"X-Orion-Admin-Key": "wrong-key"},
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    )
    assert res.status_code == 401


def test_start_rejects_unknown_vertical(client):
    res = start(client, vertical="not-a-real-vertical")
    assert res.status_code == 422
    assert res.json()["detail"] == "unknown_vertical"


def test_start_creates_pending_session_without_calling(client):
    """/start only creates the session (build spec Section 3: authorization
    must happen before the call is placed) - it never touches Twilio, so it
    succeeds even though Twilio isn't configured in the test environment."""
    res = start(client)
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "Comcast"
    assert body["status"] == "pending"
    assert body["call_sid"] is None

    listed = client.get("/api/negotiations", headers=ADMIN_HEADERS).json()
    assert len(listed) == 1
    assert listed[0]["task_id"] == body["task_id"]


def test_call_requires_admin_key(client):
    task_id = _seed_session(client)
    res = client.post(f"/api/negotiations/{task_id}/call")
    assert res.status_code == 401


def test_call_404_for_unknown_id(client):
    res = client.post("/api/negotiations/does-not-exist/call", headers=ADMIN_HEADERS)
    assert res.status_code == 404


def test_call_returns_409_when_not_authorized(client):
    task_id = _seed_session(client)
    res = client.post(f"/api/negotiations/{task_id}/call", headers=ADMIN_HEADERS)
    assert res.status_code == 409
    assert res.json()["detail"] == "not_authorized"


def test_call_without_twilio_returns_503_once_authorized(client):
    """Proves the call flow gets all the way to the Twilio call once the
    authorization guard passes - Twilio itself isn't configured in tests."""
    task_id = _seed_session(client)
    _authorize(task_id)

    res = client.post(f"/api/negotiations/{task_id}/call", headers=ADMIN_HEADERS)
    assert res.status_code == 503
    assert res.json()["detail"] == "twilio_not_configured"

    refetched = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
    assert refetched["status"] == "failed"


def test_list_negotiations_requires_admin_key(client):
    res = client.get("/api/negotiations")
    assert res.status_code == 401


def test_a_new_account_starts_with_worked_examples(client):
    """Not empty any more: a brand new account is seeded with examples so the
    dashboard has something to show. They are all flagged as samples, and the
    dashboard leaves them out of every total."""
    res = client.get("/api/negotiations", headers=ADMIN_HEADERS)
    assert res.status_code == 200

    rows = res.json()
    assert len(rows) == 5
    assert all(row["is_sample"] for row in rows)


def test_get_negotiation_requires_admin_key(client):
    task_id = _seed_session(client)
    res = client.get(f"/api/negotiations/{task_id}")
    assert res.status_code == 401


def test_get_negotiation_404_for_unknown_id(client):
    res = client.get("/api/negotiations/does-not-exist", headers=ADMIN_HEADERS)
    assert res.status_code == 404
    assert res.json()["detail"] == "not_found"


def test_complete_negotiation_requires_admin_key(client):
    task_id = _seed_session(client)
    res = client.post(f"/api/negotiations/{task_id}/complete", json={"outcome": "n/a"})
    assert res.status_code == 401


def test_complete_negotiation_404_for_unknown_id(client):
    res = client.post(
        "/api/negotiations/does-not-exist/complete", headers=ADMIN_HEADERS, json={"outcome": "n/a"}
    )
    assert res.status_code == 404


def test_complete_negotiation_records_outcome_and_persists(client):
    task_id = _seed_session(client)

    res = client.post(
        f"/api/negotiations/{task_id}/complete",
        headers=ADMIN_HEADERS,
        json={"outcome": "reduced rate", "previous_rate": 89.99, "new_rate": 69.99, "confirmation_number": "CONF1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed"
    assert body["verified"] is True
    assert body["previous_rate"] == 89.99
    assert body["new_rate"] == 69.99
    assert body["confirmation_number"] == "CONF1"

    # Persisted, not just returned in the response.
    refetched = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
    assert refetched["status"] == "completed"
    assert refetched["verified"] is True


def test_charge_requires_admin_key(client):
    task_id = _seed_session(client)
    res = client.post(f"/api/negotiations/{task_id}/charge")
    assert res.status_code == 401


def test_charge_404_for_unknown_id(client):
    res = client.post("/api/negotiations/does-not-exist/charge", headers=ADMIN_HEADERS)
    assert res.status_code == 404


def test_charge_before_verification_returns_409(client):
    task_id = _seed_session(client)
    res = client.post(f"/api/negotiations/{task_id}/charge", headers=ADMIN_HEADERS)
    assert res.status_code == 409
    assert res.json()["detail"] == "not_yet_verified"


def test_charge_with_no_savings_returns_422(client):
    task_id = _seed_session(client)
    client.post(
        f"/api/negotiations/{task_id}/complete",
        headers=ADMIN_HEADERS,
        json={"outcome": "no change", "previous_rate": 50, "new_rate": 50},
    )
    res = client.post(f"/api/negotiations/{task_id}/charge", headers=ADMIN_HEADERS)
    assert res.status_code == 422
    assert res.json()["detail"] == "no_savings_to_charge"


def test_charge_with_real_savings_hits_stripe_not_configured(client):
    """Proves the charge flow gets all the way to the Stripe call once the
    verification guards pass - Stripe itself isn't configured in tests."""
    task_id = _seed_session(client)
    client.post(
        f"/api/negotiations/{task_id}/complete",
        headers=ADMIN_HEADERS,
        json={"outcome": "reduced rate", "previous_rate": 80, "new_rate": 60},
    )
    res = client.post(f"/api/negotiations/{task_id}/charge", headers=ADMIN_HEADERS)
    assert res.status_code == 503
    assert res.json()["detail"] == "stripe_not_configured"
