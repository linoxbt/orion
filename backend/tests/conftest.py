import os

# Must happen before app.config is imported anywhere (Settings() reads env at
# import time) - overrides whatever's in backend/.env for the test session.
# Every integration secret is forced here, not just ADMIN_API_KEY: a developer
# running `pytest` locally with a fully-populated .env would otherwise get
# Settings() picking up real credentials, causing tests that assert "not
# configured" behavior to instead make live (and for AssemblyAI/Gemini/Stripe,
# billable) calls to the real APIs. AssemblyAI matters most here: an
# un-terminated streaming session bills until the 3-hour cap.
os.environ["ADMIN_API_KEY"] = "test-admin-key"
for _key in (
    "ASSEMBLYAI_API_KEY",
    "ACCOUNT_ENCRYPTION_KEY",
    "GEMINI_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "STRIPE_SECRET_KEY",
    "DOCUSIGN_INTEGRATION_KEY",
    "DOCUSIGN_USER_ID",
    "DOCUSIGN_ACCOUNT_ID",
    "DOCUSIGN_PRIVATE_KEY",
):
    os.environ[_key] = ""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ADMIN_KEY = "test-admin-key"
TEST_USER = "dyn-user-1"

# User-scoped endpoints need both: the admin key proves the request came
# through the Next proxy, and the user header says who it is for. See
# app/security.py's require_user_id for why that identity can be trusted.
ADMIN_HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": TEST_USER}

# For asserting that admin-only endpoints don't leak into user scope.
ADMIN_ONLY_HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY}


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file - no cross-test pollution,
    and never touches the real dev orion.db."""
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test.db"))


@pytest.fixture
def client(isolated_db):
    with TestClient(app) as c:
        yield c
