"""Bill extraction, and the path from an uploaded bill into the agent's prompt.

The failures these cover all reached the browser as the same unreadable
"Failed to fetch": Gemini answering 503 under load, Gemini rejecting a file
with 400, and an unrecognised MIME type. Each now has its own status and a
message that says what to do next.
"""

import pytest

from app.models import BillExtraction, LineItem, NegotiationSession
from app.routers.bills import EXTENSION_MIME, _mime_for
from app.services import prompting
from tests.conftest import ADMIN_HEADERS


class _Upload:
    """Stands in for UploadFile - only filename and content_type are read."""

    def __init__(self, filename: str, content_type: str | None):
        self.filename = filename
        self.content_type = content_type


class TestMimeDetection:
    def test_extension_wins_over_a_vague_browser_content_type(self):
        """Browsers report application/octet-stream for .PDF often enough that
        trusting content_type made Gemini reject valid bills with a 400."""
        assert _mime_for(_Upload("bill.PDF", "application/octet-stream")) == "application/pdf"

    @pytest.mark.parametrize("extension,expected", sorted(EXTENSION_MIME.items()))
    def test_known_extensions_map(self, extension, expected):
        assert _mime_for(_Upload(f"bill.{extension}", None)) == expected

    def test_falls_back_to_a_credible_content_type(self):
        assert _mime_for(_Upload("scan", "image/png")) == "image/png"

    def test_an_office_document_says_what_to_do_instead(self):
        """"Unsupported" leaves someone stuck; naming the fix doesn't."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _mime_for(_Upload("notes.docx", "application/vnd.openxmlformats"))
        assert exc.value.status_code == 422
        assert "convert_first" in exc.value.detail
        assert "PDF" in exc.value.detail

    def test_rejects_something_genuinely_unreadable(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _mime_for(_Upload("archive.zip", "application/zip"))
        assert "unsupported_file_type" in exc.value.detail

    def test_screenshots_and_scans_are_all_accepted(self):
        """Most people photograph a bill rather than exporting a PDF."""
        for name in ("bill.HEIC", "scan.tiff", "shot.webp", "photo.avif", "export.csv"):
            assert _mime_for(_Upload(name, None))

    def test_a_text_content_type_is_trusted_as_a_fallback(self):
        assert _mime_for(_Upload("statement", "text/plain")) == "text/plain"


class TestExtractionEndpoint:
    def test_returns_503_when_gemini_is_unconfigured(self, client):
        res = client.post(
            "/api/bills/ingest", headers=ADMIN_HEADERS, files={"file": ("bill.pdf", b"%PDF-1.4", "application/pdf")}
        )
        assert res.status_code == 503
        assert res.json()["detail"] == "gemini_not_configured"

    def test_unsupported_type_is_rejected_before_gemini_is_called(self, client):
        """422 rather than 503: the file is the problem, not the server."""
        res = client.post(
            "/api/bills/ingest", headers=ADMIN_HEADERS, files={"file": ("notes.docx", b"x", "application/msword")}
        )
        assert res.status_code == 422


class TestBillReachesTheAgent:
    def _session(self, **bill_kwargs) -> NegotiationSession:
        return NegotiationSession(
            task_id="t1",
            provider="Comcast",
            phone_number="+15551234567",
            vertical="cable_internet",
            bill=BillExtraction(provider="Comcast", **bill_kwargs),
        )

    def test_prompt_quotes_the_real_rate(self):
        """Without this the agent walks into the call knowing only a name."""
        prompt = prompting.system_instruction(
            self._session(current_rate=89.99, currency="USD", plan_details="Gigabit Extra")
        )
        assert "89.99" in prompt
        assert "Gigabit Extra" in prompt

    def test_prompt_names_the_line_items(self):
        """Fees are routinely waived when the base rate won't move, so the
        agent has to be able to name them."""
        prompt = prompting.system_instruction(
            self._session(
                line_items=[
                    LineItem(description="Broadcast TV Fee", amount=27.0),
                    LineItem(description="Equipment rental", amount=15.0),
                ]
            )
        )
        assert "Broadcast TV Fee" in prompt
        assert "Equipment rental" in prompt

    def test_prompt_carries_leverage_facts(self):
        prompt = prompting.system_instruction(
            self._session(contract_end_date="2026-11-30", customer_since="2019")
        )
        assert "2026-11-30" in prompt
        assert "2019" in prompt

    def test_prompt_forbids_inventing_numbers(self):
        prompt = prompting.system_instruction(self._session(current_rate=50.0))
        assert "never invent a number" in prompt.lower()

    def test_no_bill_leaves_the_prompt_intact(self):
        """A negotiation started without an upload must still work."""
        session = NegotiationSession(
            task_id="t2", provider="Verizon", phone_number="+15551234567", vertical="cell_phone"
        )
        prompt = prompting.system_instruction(session)
        assert "Verizon" in prompt
        assert "bill in front of you" not in prompt


class TestBillSeedsTheVault:
    def test_account_details_are_taken_from_the_bill(self, client, monkeypatch):
        """The extraction already read the account number - making the customer
        retype it would be the kind of friction this product exists to remove."""
        from app.config import settings
        from app.services import account_vault

        monkeypatch.setattr(
            settings, "account_encryption_key", "eOZgpLbnEQKDpP0h7lHIqNfLqiHmuoiPFGpbrzu3D0M="
        )
        account_vault._cipher.cache_clear()

        res = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Comcast",
                "phone_number": "+15551234567",
                "vertical": "cable_internet",
                "bill": {
                    "provider": "Comcast",
                    "account_number": "8495 10 123 4567890",
                    "account_holder_name": "A. Customer",
                    "current_rate": 89.99,
                },
            },
        )
        assert res.status_code == 200
        task_id = res.json()["task_id"]

        fields = client.get(
            f"/api/negotiations/{task_id}/account-details", headers=ADMIN_HEADERS
        ).json()["fields"]
        assert "account_number" in fields
        assert "account_holder_name" in fields
        account_vault._cipher.cache_clear()

    def test_starting_without_a_vault_key_still_works(self, client):
        """A missing key must cost verification, not the whole negotiation."""
        res = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Comcast",
                "phone_number": "+15551234567",
                "vertical": "cable_internet",
                "bill": {"provider": "Comcast", "account_number": "123", "current_rate": 50.0},
            },
        )
        assert res.status_code == 200
        assert res.json()["bill"]["current_rate"] == 50.0

    def test_the_bill_is_stored_on_the_session(self, client):
        res = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Comcast",
                "phone_number": "+15551234567",
                "vertical": "cable_internet",
                "bill": {
                    "provider": "Comcast",
                    "current_rate": 89.99,
                    "line_items": [{"description": "Broadcast TV Fee", "amount": 27.0}],
                },
            },
        )
        task_id = res.json()["task_id"]

        fetched = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
        assert fetched["bill"]["line_items"][0]["description"] == "Broadcast TV Fee"


class TestNegotiabilityFlag:
    def test_a_retail_receipt_is_not_negotiable_by_default(self):
        """A Temu receipt has a merchant and a total but nothing recurring to
        argue down, and saying so beats returning a row of blanks."""
        bill = BillExtraction(provider="TEMU", document_type="retail_receipt")
        assert bill.is_negotiable is False

    def test_defaults_are_safe_when_the_model_omits_them(self):
        bill = BillExtraction(provider="Anything")
        assert bill.document_type == "unknown"
        assert bill.is_negotiable is False
        assert bill.line_items == []


class TestConsentUnblocksCalling:
    """The call button only rendered when session.authorized was true, and the
    only route to authorized was DocuSign - which was never configured, so the
    button was unreachable by construction and no call could ever be placed.
    In-app consent replaced it; the DocuSign path has since been deleted.
    """

    def _start(self, client) -> str:
        return client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Comcast",
                "phone_number": "+15551234567",
                "vertical": "cable_internet",
            },
        ).json()["task_id"]

    def test_a_session_starts_unauthorized(self, client):
        task_id = self._start(client)
        assert client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()["authorized"] is False

    def test_in_app_consent_authorizes_the_session(self, client):
        task_id = self._start(client)
        res = client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=ADMIN_HEADERS,
            json={"signer_name": "A. Customer", "agreed": True},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["authorized"] is True
        assert body["consent_signer_name"] == "A. Customer"
        # What someone agreed to has to be reconstructable later.
        assert body["consent_version"]
        assert body["consent_at"]

    def test_consent_is_refused_without_agreement(self, client):
        task_id = self._start(client)
        res = client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=ADMIN_HEADERS,
            json={"signer_name": "A. Customer", "agreed": False},
        )
        assert res.status_code == 422

    def test_consent_is_refused_without_a_name(self, client):
        task_id = self._start(client)
        res = client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=ADMIN_HEADERS,
            json={"signer_name": "   ", "agreed": True},
        )
        assert res.status_code == 422

    def test_calling_gets_past_the_consent_gate_once_authorized(self, client):
        """It still 503s on Twilio, which is a different, honest problem - the
        point is that it is no longer refused for lack of authorisation."""
        task_id = self._start(client)
        client.post(
            f"/api/negotiations/{task_id}/consent",
            headers=ADMIN_HEADERS,
            json={"signer_name": "A. Customer", "agreed": True},
        )
        res = client.post(f"/api/negotiations/{task_id}/call", headers=ADMIN_HEADERS)
        assert res.status_code != 409
        assert res.json()["detail"] == "twilio_not_configured"


class TestObjectiveDrivesTheCall:
    """Orion is not only a bill-reduction agent. Asking a marketplace to lower
    the monthly rate on a one-off purchase would be nonsense, so the document
    decides what the call is for."""

    def _prompt(self, objective: str, summary: str | None = None) -> str:
        session = NegotiationSession(
            task_id="t",
            provider="TEMU",
            phone_number="+15551234567",
            vertical="cable_internet",
            bill=BillExtraction(
                provider="TEMU", call_objective=objective, objective_summary=summary
            ),
        )
        return prompting.system_instruction(session)

    def test_refund_objective_asks_for_money_back(self):
        prompt = self._prompt("request_refund")
        assert "refund" in prompt.lower()
        assert "money back" in prompt.lower()

    def test_cancellation_objective_asks_about_termination_fees(self):
        assert "termination" in self._prompt("cancel_service").lower()

    def test_dispute_objective_asks_for_a_reversal(self):
        assert "revers" in self._prompt("dispute_charge").lower()

    def test_payment_plan_objective_asks_about_hardship(self):
        assert "hardship" in self._prompt("payment_plan").lower()

    def test_the_specific_ask_is_carried_into_the_prompt(self):
        prompt = self._prompt("waive_fees", "Ask for the $27 broadcast TV fee to be waived.")
        assert "broadcast TV fee" in prompt

    def test_an_unknown_objective_falls_back_rather_than_crashing(self):
        assert self._prompt("something_new_the_model_invented")


class TestModelFallback:
    """The reason extraction kept failing: one model was pinned, and when it
    answered 503 "experiencing high demand" the code retried the same model
    four times and gave up. A saturated model stays saturated for minutes."""

    def test_more_than_one_model_is_configured(self):
        from app.config import settings

        assert len(settings.gemini_model_chain) > 1

    def test_the_saturated_model_is_no_longer_first(self):
        """gemini-flash-latest returned 503 on every attempt over six minutes
        while three other models answered immediately."""
        from app.config import settings

        assert settings.gemini_model_chain[0] != "gemini-flash-latest"

    def test_gemini_model_still_resolves_for_single_model_callers(self):
        from app.config import settings

        assert settings.gemini_model == settings.gemini_model_chain[0]


class TestUploadsAreBounded:
    """The size check used to happen after the whole file had been read, so a
    request could spool an unbounded amount to disk before being refused."""

    def test_an_oversized_upload_is_refused(self, client):
        from app.routers.bills import MAX_BYTES

        res = client.post(
            "/api/bills/ingest",
            headers=ADMIN_HEADERS,
            files={"file": ("huge.pdf", b"x" * (MAX_BYTES + 1024), "application/pdf")},
        )
        assert res.status_code == 413
        assert "file_too_large" in res.json()["detail"]

    def test_an_empty_upload_is_refused(self, client):
        res = client.post(
            "/api/bills/ingest",
            headers=ADMIN_HEADERS,
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "empty_file"
