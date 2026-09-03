"""Tests for what a real provider line demands: a keypad, and proof of identity.

The mock rep answered politely on the first ring. A real retention line opens
with a menu and then asks who is calling, so these cover the two pieces that
stand between Orion and a human: DTMF, and account verification.
"""

import audioop
import struct

import pytest

from app.config import settings
from app.models import NegotiationSession
from app.services import account_vault, call_tools, prompting
from app.services.dtmf import GAP_MS, SAMPLE_RATE, TONE_MS, keys_to_mulaw, linear_to_ulaw

# Generated for the test run only; never a real key.
TEST_KEY = "eOZgpLbnEQKDpP0h7lHIqNfLqiHmuoiPFGpbrzu3D0M="


@pytest.fixture
def session() -> NegotiationSession:
    return NegotiationSession(
        task_id="task-1", provider="Comcast", phone_number="+15551234567", vertical="cable_internet"
    )


@pytest.fixture(autouse=True)
def _isolate_cipher():
    """The Fernet cipher is lru_cached, so a test that sets a key would
    otherwise leak one into a later test asserting the key is absent."""
    account_vault._cipher.cache_clear()
    yield
    account_vault._cipher.cache_clear()


@pytest.fixture
def vault(monkeypatch):
    monkeypatch.setattr(settings, "account_encryption_key", TEST_KEY)
    account_vault._cipher.cache_clear()


class TestMulawEncoder:
    def test_matches_the_reference_across_the_entire_int16_range(self):
        """G.711 is defined on 14-bit magnitudes. Skipping that shift produces
        output that is right across most of the range and wrong near full
        scale - audible only on loud tones, which is exactly what DTMF is."""
        mismatches = sum(
            1
            for sample in range(-32768, 32768)
            if linear_to_ulaw(sample) != audioop.lin2ulaw(struct.pack("<h", sample), 2)[0]
        )
        assert mismatches == 0

    def test_digital_silence_is_0xff_not_0x00(self):
        """0x00 in mu-law is full-scale noise; padding a gap with it would put a
        burst of static on the line between digits."""
        assert linear_to_ulaw(0) == 0xFF


class TestKeypadAudio:
    def test_one_digit_is_a_tone_plus_a_gap(self):
        expected = SAMPLE_RATE * (TONE_MS + GAP_MS) // 1000
        assert len(keys_to_mulaw("1")) == expected

    def test_each_digit_gets_its_own_tone(self):
        assert len(keys_to_mulaw("123")) == 3 * len(keys_to_mulaw("1"))

    def test_comma_inserts_a_pause(self):
        assert len(keys_to_mulaw("1,2")) > len(keys_to_mulaw("12"))

    def test_distinct_digits_produce_distinct_audio(self):
        """A row/column mix-up would make every digit sound plausible and dial
        the wrong menu option."""
        assert keys_to_mulaw("1") != keys_to_mulaw("2")
        assert keys_to_mulaw("1") != keys_to_mulaw("4")

    def test_unusable_characters_are_skipped_not_raised(self):
        assert keys_to_mulaw("1!2") == keys_to_mulaw("12")
        assert keys_to_mulaw("!!!") == b""


class TestPressKeysTool:
    @pytest.mark.parametrize("keys", ["2", "1,0", "#"])
    def test_sends_audio_to_the_call(self, session, isolated_db, keys):
        sent: list[bytes] = []

        async def sink(audio: bytes) -> None:
            sent.append(audio)

        result = _dispatch(session, "press_keys", {"keys": keys}, audio_sink=sink)
        assert "Pressed" in result
        assert sent and len(sent[0]) > 0

    def test_refuses_when_there_is_no_keypad(self, session, isolated_db):
        """The stt backend passes a sink; a caller that doesn't must get a clear
        refusal rather than a silent success the agent then believes."""
        result = _dispatch(session, "press_keys", {"keys": "2"}, audio_sink=None)
        assert "isn't available" in result

    def test_rejects_a_sequence_with_no_real_digits(self, session, isolated_db):
        sent: list[bytes] = []

        async def sink(audio: bytes) -> None:
            sent.append(audio)

        result = _dispatch(session, "press_keys", {"keys": "hello"}, audio_sink=sink)
        assert "no usable keypad digits" in result
        assert sent == []


class TestAccountVault:
    def test_round_trips_only_known_fields(self, vault):
        sealed = account_vault.seal(
            {"account_number": "12345678", "security_pin": "4821", "not_a_field": "x"}
        )
        opened = account_vault.unseal(sealed)
        assert opened == {"account_number": "12345678", "security_pin": "4821"}

    def test_ciphertext_does_not_contain_the_secret(self, vault):
        sealed = account_vault.seal({"security_pin": "4821"})
        assert "4821" not in sealed

    def test_unreadable_blob_degrades_instead_of_raising(self, vault):
        """A rotated key must mean 'Orion can't verify', not a crashed call."""
        assert account_vault.unseal("not-a-real-fernet-token") == {}
        assert account_vault.unseal(None) == {}

    def test_refuses_to_store_without_a_key(self, monkeypatch):
        """Failing closed matters more than convenience here - the alternative
        is writing a security PIN to disk in the clear."""
        monkeypatch.setattr(settings, "account_encryption_key", "")
        account_vault._cipher.cache_clear()
        with pytest.raises(account_vault.VaultNotConfigured):
            account_vault.seal({"security_pin": "4821"})
        account_vault._cipher.cache_clear()

    def test_available_fields_lists_names_only(self, vault):
        sealed = account_vault.seal({"account_number": "12345678", "security_pin": "4821"})
        assert account_vault.available_fields(sealed) == ["account_number", "security_pin"]


class TestVerificationTool:
    def test_returns_the_requested_field(self, session, isolated_db, vault):
        session.account_details = account_vault.seal({"security_pin": "4821"})
        assert _dispatch(session, "provide_verification", {"field": "security_pin"}) == "4821"

    def test_refuses_a_field_that_is_not_on_file(self, session, isolated_db, vault):
        session.account_details = account_vault.seal({"account_number": "12345678"})
        result = _dispatch(session, "provide_verification", {"field": "security_pin"})
        assert "not on file" in result

    def test_handles_a_session_with_no_details_at_all(self, session, isolated_db):
        result = _dispatch(session, "provide_verification", {"field": "security_pin"})
        assert "not on file" in result


class TestPromptSafety:
    def test_prompt_names_the_available_fields(self, session, vault):
        session.account_details = account_vault.seal(
            {"account_number": "12345678", "security_pin": "4821"}
        )
        prompt = prompting.system_instruction(session)
        assert "the account number" in prompt
        assert "the account security PIN" in prompt

    def test_prompt_never_contains_the_values(self, session, vault):
        """The whole reason verification goes through a tool: a value in the
        system prompt is a value the model can volunteer unprompted."""
        session.account_details = account_vault.seal(
            {"account_number": "12345678", "security_pin": "4821", "last4_ssn": "6789"}
        )
        prompt = prompting.system_instruction(session)
        for secret in ("12345678", "4821", "6789"):
            assert secret not in prompt

    def test_prompt_tells_the_agent_to_escalate_when_it_has_nothing(self, session):
        prompt = prompting.system_instruction(session)
        assert "no account verification details on file" in prompt

    def test_prompt_covers_menus_and_hold(self, session):
        prompt = prompting.system_instruction(session)
        assert "press_keys" in prompt
        assert "hold" in prompt.lower()


class TestAccountDetailsApi:
    def test_details_are_never_returned_by_the_read_api(self, client, monkeypatch):
        monkeypatch.setattr(settings, "account_encryption_key", TEST_KEY)
        account_vault._cipher.cache_clear()
        from tests.conftest import ADMIN_HEADERS

        task_id = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        ).json()["task_id"]

        stored = client.post(
            f"/api/negotiations/{task_id}/account-details",
            headers=ADMIN_HEADERS,
            json={"account_number": "12345678", "security_pin": "4821"},
        )
        assert stored.status_code == 200
        assert "account_details" not in stored.json()

        fetched = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS)
        body = fetched.text
        assert "account_details" not in fetched.json()
        assert "4821" not in body and "12345678" not in body

        listed = client.get(f"/api/negotiations/{task_id}/account-details", headers=ADMIN_HEADERS)
        assert listed.json() == {"fields": ["account_number", "security_pin"]}
        account_vault._cipher.cache_clear()

    def test_rejects_an_empty_submission(self, client, monkeypatch):
        monkeypatch.setattr(settings, "account_encryption_key", TEST_KEY)
        account_vault._cipher.cache_clear()
        from tests.conftest import ADMIN_HEADERS

        task_id = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        ).json()["task_id"]

        res = client.post(
            f"/api/negotiations/{task_id}/account-details", headers=ADMIN_HEADERS, json={}
        )
        assert res.status_code == 422
        account_vault._cipher.cache_clear()

    def test_refuses_when_the_vault_has_no_key(self, client):
        """Better a 503 than silently persisting a PIN in plaintext."""
        from tests.conftest import ADMIN_HEADERS

        task_id = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        ).json()["task_id"]

        res = client.post(
            f"/api/negotiations/{task_id}/account-details",
            headers=ADMIN_HEADERS,
            json={"security_pin": "4821"},
        )
        assert res.status_code == 503
        assert res.json()["detail"] == "account_vault_not_configured"


def _dispatch(session, name, arguments, audio_sink=None):
    """Drive the async tool dispatcher from a synchronous test."""
    import asyncio

    from app.store import init_db

    async def run():
        await init_db()
        return await call_tools.dispatch(session, name, arguments, audio_sink=audio_sink)

    return asyncio.run(run())
