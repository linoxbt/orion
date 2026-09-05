"""Which Dynamic environment this deployment is actually using.

Found the expensive way: a login code for Orion arrived branded "Devstation",
because the frontend, the backend and CI all pointed at another project's
sandbox environment. Nothing in the app could show that - the environment id is
an opaque uuid, and the SDK's own appName only labels the widget - so the first
sign that anything was wrong was the email itself.

The check below is what makes that visible at boot instead.
"""

import asyncio
import logging

from app.config import settings
from app import security


def _fake_settings_endpoint(monkeypatch, payload=None, boom: Exception | None = None):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            if boom is not None:
                raise boom
            return Response()

    monkeypatch.setattr(security.httpx, "AsyncClient", lambda **kw: Client())


def _run(monkeypatch, caplog, **kwargs) -> str:
    monkeypatch.setattr(settings, "dynamic_environment_id", "env-1")
    _fake_settings_endpoint(monkeypatch, **kwargs)
    with caplog.at_level(logging.INFO):
        asyncio.run(security.check_dynamic_environment())
    return caplog.text


class TestEnvironmentCheck:
    def test_the_right_environment_logs_and_says_nothing_else(self, monkeypatch, caplog):
        text = _run(
            monkeypatch,
            caplog,
            payload={"general": {"displayName": "Orion"}, "environmentName": "live"},
        )
        assert "Dynamic environment: Orion (live)" in text
        assert "WARNING" not in text

    def test_another_projects_environment_warns_by_name(self, monkeypatch, caplog):
        text = _run(
            monkeypatch,
            caplog,
            payload={"general": {"displayName": "Devstation"}, "environmentName": "live"},
        )
        assert "Devstation" in text
        assert "login codes are emailed" in text

    def test_a_sandbox_environment_warns(self, monkeypatch, caplog):
        text = _run(
            monkeypatch,
            caplog,
            payload={"general": {"displayName": "Orion"}, "environmentName": "sandbox"},
        )
        assert "development environment" in text

    def test_an_unreachable_endpoint_does_not_stop_the_app(self, monkeypatch, caplog):
        # Startup must survive this: sessions are verified against the JWKS, and
        # a diagnostic that cannot run is not a reason to refuse to serve.
        text = _run(monkeypatch, caplog, boom=RuntimeError("no route to host"))
        assert "Could not read the Dynamic environment" in text

    def test_an_unconfigured_environment_is_left_alone(self, monkeypatch, caplog):
        """check_jwks_reachable already says the id is missing; saying it twice
        on every boot is noise."""
        monkeypatch.setattr(settings, "dynamic_environment_id", "")
        called = False

        def fail(**kw):
            nonlocal called
            called = True
            raise AssertionError("no HTTP call should be made")

        monkeypatch.setattr(security.httpx, "AsyncClient", fail)
        with caplog.at_level(logging.INFO):
            asyncio.run(security.check_dynamic_environment())
        assert not called

    def test_it_reads_the_environment_it_was_configured_with(self, monkeypatch):
        monkeypatch.setattr(settings, "dynamic_environment_id", "env-abc")
        assert security.settings_url().endswith("/sdk/env-abc/settings")
