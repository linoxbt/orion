"""The operator console's door.

Two things were wrong with it. The cookie was the admin key itself - the
credential that places calls and charges cards - parked in a browser for a
month. And the sign-in form accepted guesses as fast as they could be sent:
five wrong keys in a row answered 200 five times, with nothing logged and no
delay, against a backend that is on the public internet.
"""

import time

import pytest

from app.routers.dashboard import _authorised, _mint_session
from app.services import ratelimit
from tests.conftest import ADMIN_KEY


class _Request:
    def __init__(self, cookie: str | None):
        self.cookies = {"orion_admin": cookie} if cookie else {}


@pytest.fixture(autouse=True)
def _clean_limiter():
    ratelimit.reset()
    yield
    ratelimit.reset()


class TestTheCookieIsNotTheKey:
    def test_the_admin_key_is_not_accepted_as_a_session(self, client):
        """Whatever else changes, the key itself must stop working as a cookie -
        otherwise the old one lying in a browser is still a valid session."""
        assert _authorised(_Request(ADMIN_KEY)) is False

    def test_a_minted_session_is_accepted(self, client):
        assert _authorised(_Request(_mint_session())) is True

    def test_an_expired_session_is_refused(self, client):
        assert _authorised(_Request(_mint_session(now=time.time() - 40 * 24 * 3600))) is False

    def test_a_tampered_expiry_is_refused(self, client):
        token = _mint_session()
        _, _, digest = token.partition(".")
        forged = f"{int(time.time()) + 10 * 365 * 24 * 3600}.{digest}"
        assert _authorised(_Request(forged)) is False

    def test_nonsense_is_refused(self, client):
        for junk in ("", "guessed", "abc.def", "..", "9999999999"):
            assert _authorised(_Request(junk)) is False

    def test_the_key_never_appears_in_a_cookie(self, client):
        res = client.post("/admin/login", data={"key": ADMIN_KEY}, follow_redirects=False)
        assert res.status_code == 303
        assert ADMIN_KEY not in res.headers.get("set-cookie", "")


class TestGuessingIsThrottled:
    def test_repeated_wrong_keys_are_rate_limited(self, client):
        codes = [
            client.post("/admin/login", data={"key": f"wrong-{i}"}, follow_redirects=False).status_code
            for i in range(8)
        ]
        assert 429 in codes, f"unlimited guessing allowed: {codes}"

    def test_the_limit_does_not_lock_out_a_correct_key_first(self, client):
        res = client.post("/admin/login", data={"key": ADMIN_KEY}, follow_redirects=False)
        assert res.status_code == 303
