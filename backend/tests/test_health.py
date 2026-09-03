from tests.conftest import ADMIN_HEADERS, ADMIN_ONLY_HEADERS


def test_health_is_public_and_reveals_nothing(client):
    """Liveness has to be reachable without credentials, but which integrations
    are configured is operational detail, not something to hand to anyone who
    curls the URL."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "version": "0.1.0"}
    assert "capabilities" not in res.json()


def test_capabilities_require_the_admin_key(client):
    assert client.get("/health/capabilities").status_code == 401


def test_capabilities_report_everything_unconfigured_under_test(client):
    res = client.get("/health/capabilities", headers=ADMIN_ONLY_HEADERS)
    assert res.status_code == 200
    assert res.json()["capabilities"] == {
        "hasAssemblyAI": False,
        "voiceBackend": "agent_api",
        "hasGemini": False,
        "hasTwilio": False,
        "hasStripe": False,
        # No Dynamic environment under test, so sessions cannot be verified.
        "sessionsVerifiable": False,
        # No Supabase under test either.
        "persistence": "sqlite",
    }
