"""The operator dashboard, and the fact that it is not public.

It shows customer accounts, negotiations and payment references, so the
interesting question is not whether it renders but whether a stranger can
reach it.
"""

import pytest

from app.config import settings
from app.routers import dashboard
from tests.conftest import ADMIN_KEY


class TestAccess:
    def test_a_stranger_gets_a_sign_in_form_not_data(self, client):
        res = client.get("/admin")
        assert res.status_code == 200
        assert "Sign in" in res.text
        # None of the real content leaks into the unauthenticated page.
        for leak in ("Recent negotiations", "Payments", "Integrations"):
            assert leak not in res.text

    def test_the_root_leads_to_the_dashboard(self, client):
        res = client.get("/", follow_redirects=False)
        assert res.status_code in (302, 303, 307)
        assert res.headers["location"] == "/admin"

    def test_a_wrong_key_is_refused(self, client):
        res = client.post("/admin/login", data={"key": "not-the-key"}, follow_redirects=False)
        assert res.status_code == 200
        assert "was not accepted" in res.text
        assert "orion_admin" not in res.headers.get("set-cookie", "")

    def test_the_right_key_signs_you_in(self, client):
        res = client.post("/admin/login", data={"key": ADMIN_KEY}, follow_redirects=False)
        assert res.status_code == 303
        cookie = res.headers.get("set-cookie", "")
        assert "orion_admin" in cookie
        # The cookie carries the key, so script access and plain HTTP are both
        # closed off, and another site cannot navigate a browser into using it.
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "lax" in cookie.lower()

    def test_a_forged_cookie_is_refused(self, client):
        client.cookies.set("orion_admin", "guessed")
        res = client.get("/admin")
        assert "Sign in" in res.text

    def test_signing_out_clears_the_cookie(self, client):
        client.cookies.set("orion_admin", ADMIN_KEY)
        res = client.get("/admin/logout", follow_redirects=False)
        assert res.status_code == 303
        assert 'orion_admin=""' in res.headers.get("set-cookie", "") or \
               "orion_admin=;" in res.headers.get("set-cookie", "")

    def test_an_unconfigured_deployment_admits_nobody(self, client, monkeypatch):
        """An unset admin key must not become a blank password that lets
        anyone in."""
        monkeypatch.setattr(settings, "admin_api_key", "")
        res = client.post("/admin/login", data={"key": "anything"}, follow_redirects=False)
        assert "was not accepted" in res.text

    def test_the_cookie_is_not_accepted_over_plain_http(self, client):
        """Not a test quirk: the cookie is Secure, so a browser will not send
        it over http at all. Production is https; this pins the intent."""
        res = client.post("/admin/login", data={"key": ADMIN_KEY}, follow_redirects=False)
        assert "Secure" in res.headers.get("set-cookie", "")


class TestRendering:
    def test_it_renders_with_real_data(self, client):
        client.cookies.set("orion_admin", ADMIN_KEY)
        res = client.get("/admin")
        assert res.status_code == 200
        for section in ("Protocol", "Money", "Integrations", "Recent negotiations", "Payments"):
            assert section in res.text

    def test_it_never_prints_a_secret(self, client):
        client.cookies.set("orion_admin", ADMIN_KEY)
        body = client.get("/admin").text
        assert ADMIN_KEY not in body
        for secret in (settings.assemblyai_api_key, settings.gemini_api_key,
                       settings.paystack_secret_key, settings.supabase_service_key):
            if secret:
                assert secret not in body

    def test_a_failure_to_assemble_is_shown_not_a_500(self, client, monkeypatch):
        """An operator locked out by a 500 cannot see what is wrong."""
        async def boom():
            raise RuntimeError("supabase is down")

        monkeypatch.setattr(dashboard.admin_stats, "collect", boom)
        client.cookies.set("orion_admin", ADMIN_KEY)
        res = client.get("/admin")
        assert res.status_code == 200
        assert "did not load" in res.text

    def test_html_is_escaped(self):
        assert dashboard._esc('<script>"x"</script>') == \
            "&lt;script&gt;&quot;x&quot;&lt;/script&gt;"
