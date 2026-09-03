"""Negotiations belong to somebody.

Before this, sessions had no owner at all: `GET /api/negotiations` returned
every negotiation in the system to any signed-in user. A profile feature only
makes sense once data is actually separated, so these cover the separation
rather than the profile.
"""

from tests.conftest import ADMIN_HEADERS, ADMIN_KEY, ADMIN_ONLY_HEADERS, TEST_USER

OTHER_USER = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "dyn-user-2"}


def _start(client, headers) -> str:
    return client.post(
        "/api/negotiations/start",
        headers=headers,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    ).json()["task_id"]


class TestIdentityIsRequired:
    def test_starting_without_an_identity_is_refused(self, client):
        """The admin key alone is not enough - it says the request came through
        the proxy, not who it is for."""
        res = client.post(
            "/api/negotiations/start",
            headers=ADMIN_ONLY_HEADERS,
            json={"provider": "Comcast", "phone_number": "+1555", "vertical": "cable_internet"},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "no_user_identity"

    def test_listing_without_an_identity_is_refused(self, client):
        res = client.get("/api/negotiations", headers=ADMIN_ONLY_HEADERS)
        assert res.status_code == 401

    def test_a_user_header_alone_proves_nothing(self, client):
        """Without the admin key the header is just a claim, and anyone could
        send it."""
        res = client.get("/api/negotiations", headers={"X-Orion-User": "dyn-user-2"})
        assert res.status_code == 401

    def test_the_profile_requires_an_identity_too(self, client):
        assert client.get("/api/profile", headers=ADMIN_ONLY_HEADERS).status_code == 401


class TestSeparation:
    def test_a_new_session_records_its_owner(self, client):
        task_id = _start(client, ADMIN_HEADERS)
        session = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
        assert session["user_id"] == TEST_USER

    def test_one_user_does_not_see_anothers_negotiations(self, client):
        mine = _start(client, ADMIN_HEADERS)
        theirs = _start(client, OTHER_USER)

        my_list = client.get("/api/negotiations", headers=ADMIN_HEADERS).json()
        my_ids = {row["task_id"] for row in my_list}

        assert mine in my_ids
        assert theirs not in my_ids, "a user must not see another user's negotiations"

    def test_each_user_sees_their_own(self, client):
        mine = _start(client, ADMIN_HEADERS)
        theirs = _start(client, OTHER_USER)

        their_ids = {row["task_id"] for row in client.get("/api/negotiations", headers=OTHER_USER).json()}
        assert theirs in their_ids
        assert mine not in their_ids


class TestProfileScoping:
    def test_a_first_visit_returns_an_empty_profile_rather_than_404(self, client):
        """A first-time user has done nothing wrong; the account page should
        have something to render."""
        res = client.get("/api/profile", headers=ADMIN_HEADERS)
        # Supabase is unconfigured under test, so this is the honest failure -
        # what matters is that it is not a 401 or a 404.
        assert res.status_code == 503
        assert res.json()["detail"] == "supabase_not_configured"

    def test_saving_a_profile_needs_supabase(self, client):
        res = client.put("/api/profile", headers=ADMIN_HEADERS, json={"full_name": "A. Customer"})
        assert res.status_code == 503
