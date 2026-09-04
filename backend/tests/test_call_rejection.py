"""Twilio refusing a call is the caller's problem, not a server error.

Placing a real call returned 'request_failed_500' with nothing to act on. The
actual reason was in Twilio's response the whole time: "Account not authorized
to call +234...  Perhaps you need to enable some international permissions".
"""

import pytest
from twilio.base.exceptions import TwilioRestException

from app.config import settings
from app.services import twilio_client
from app.services.twilio_client import CallRejected, _hint_for
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "owner"}


def _rest_error(code: int, msg: str) -> TwilioRestException:
    return TwilioRestException(status=400, uri="/Calls", msg=msg, code=code)


class TestHints:
    def test_geo_permissions_is_explained(self):
        exc = _rest_error(21215, "Account not authorized to call +2347000000000.")
        hint = _hint_for(exc)
        assert hint and "geo permissions" in hint.lower()

    def test_geo_permissions_is_caught_even_under_an_unlisted_code(self):
        """Twilio's own wording is the reliable signal; the code varies."""
        exc = _rest_error(99999, "Account not authorized to call +2347000000000.")
        hint = _hint_for(exc)
        assert hint and "geo permissions" in hint.lower()

    def test_an_unrecognised_error_gets_no_invented_hint(self):
        assert _hint_for(_rest_error(12345, "Something else entirely")) is None

    @pytest.mark.parametrize("code", [21210, 21211, 21219, 21606, 20003])
    def test_the_common_failures_all_say_what_to_do(self, code):
        assert _hint_for(_rest_error(code, "x"))


class TestEndpoint:
    @pytest.fixture
    def authorised(self, client, monkeypatch) -> str:
        monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "0" * 32)
        monkeypatch.setattr(settings, "twilio_auth_token", "token")
        monkeypatch.setattr(settings, "twilio_phone_number", "+15550000000")

        task_id = client.post(
            "/api/negotiations/start",
            headers=HEADERS,
            json={"provider": "Comcast", "phone_number": "+2347000000000",
                  "vertical": "cable_internet"},
        ).json()["task_id"]
        client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=HEADERS,
            json={"signer_name": "Denis", "agreed": True},
        )
        return task_id

    def test_a_refused_call_is_422_with_the_real_reason(
        self, client, authorised, monkeypatch
    ):
        def boom(session):
            raise CallRejected(
                "Account not authorized to call +2347000000000.",
                "Enable it under Voice > Settings > Geo permissions.",
            )

        monkeypatch.setattr("app.routers.negotiations.place_outbound_call", boom)

        res = client.post(f"/api/negotiations/{authorised}/call", headers=HEADERS)
        assert res.status_code == 422

        detail = res.json()["detail"]
        assert "not authorized to call" in detail
        assert "Geo permissions" in detail

    def test_the_negotiation_records_why_it_failed(
        self, client, authorised, monkeypatch
    ):
        """So the dashboard does not just show a silent 'failed'."""
        def boom(session):
            raise CallRejected("Account not authorized to call +2347000000000.")

        monkeypatch.setattr("app.routers.negotiations.place_outbound_call", boom)
        client.post(f"/api/negotiations/{authorised}/call", headers=HEADERS)

        session = client.get(f"/api/negotiations/{authorised}", headers=HEADERS).json()
        assert session["status"] == "failed"
        assert "not authorized to call" in session["outcome"]

    def test_a_rest_exception_never_escapes_as_a_500(self, client, authorised, monkeypatch):
        """The actual regression: an unhandled TwilioRestException."""
        def boom(*a, **kw):
            raise _rest_error(21215, "Account not authorized to call +2347000000000.")

        monkeypatch.setattr(twilio_client, "get_client", lambda: type(
            "C", (), {"calls": type("X", (), {"create": staticmethod(boom)})()}
        )())

        res = client.post(f"/api/negotiations/{authorised}/call", headers=HEADERS)
        assert res.status_code == 422
        assert "not authorized" in res.json()["detail"]
