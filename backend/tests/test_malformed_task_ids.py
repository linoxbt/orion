"""A task id that cannot name a row is not found, not a server error.

negotiations.task_id is a uuid column, so PostgREST answers 400 (22P02) rather
than an empty result for anything that is not a uuid. That surfaced as a 500:
GET /api/receipts/<junk> was a server error any stranger could trigger without
signing in, and the media-stream WebSocket answered a real call with 500
instead of closing cleanly.
"""

import pytest

from app.services import supabase_store
from tests.conftest import ADMIN_KEY

HEADERS = {"X-Orion-Admin-Key": ADMIN_KEY, "X-Orion-User": "someone"}

MALFORMED = [
    "not-a-uuid",
    "probe-task-not-a-real-negotiation",
    "",
    "../../etc/passwd",
    "1234",
    "00000000-0000-0000-0000-00000000000",  # one digit short
]


class TestCouldExist:
    @pytest.mark.parametrize("task_id", MALFORMED)
    def test_a_malformed_id_cannot_name_a_row(self, task_id):
        assert supabase_store._could_exist(task_id) is False

    def test_a_real_uuid_can(self):
        import uuid

        assert supabase_store._could_exist(str(uuid.uuid4())) is True

    def test_none_is_handled_rather_than_raising(self):
        assert supabase_store._could_exist(None) is False  # type: ignore[arg-type]


class TestEndpoints:
    """Through the API, so the fix is checked where the 500 actually appeared."""

    @pytest.mark.parametrize("task_id", ["not-a-uuid", "1234", "../../etc/passwd"])
    def test_a_public_receipt_lookup_is_404_not_500(self, client, task_id):
        res = client.get(f"/api/receipts/{task_id}")
        assert res.status_code == 404

    @pytest.mark.parametrize("task_id", ["not-a-uuid", "1234"])
    def test_a_negotiation_lookup_is_404_not_500(self, client, task_id):
        res = client.get(f"/api/negotiations/{task_id}", headers=HEADERS)
        assert res.status_code == 404

    def test_the_stream_closes_cleanly_rather_than_erroring(self, client):
        """This answered 500 in production, having passed the token check."""
        from starlette.websockets import WebSocketDisconnect

        from app.services.twilio_client import mint_stream_token

        task = "not-a-uuid"
        token = mint_stream_token(task)
        with pytest.raises(WebSocketDisconnect) as caught:
            with client.websocket_connect(
                f"/telephony/stream?taskId={task}&token={token}"
            ) as ws:
                ws.receive_text()
        assert caught.value.code == 1008
