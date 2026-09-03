"""The browser path: the same agent, without a phone line.

Twilio's trial tier blocks <Stream>, so on a free account this is the only way
to run a negotiation. These check that it stays the *same* agent rather than a
second, weaker one - same prompt, same tools - and that the browser never gets
handed anything it shouldn't hold.
"""

from tests.conftest import ADMIN_HEADERS


def _start(client) -> str:
    return client.post(
        "/api/negotiations/start",
        headers=ADMIN_HEADERS,
        json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
    ).json()["task_id"]


class TestBrowserSession:
    def test_requires_the_admin_key(self, client):
        res = client.post("/api/browser/some-task/session")
        assert res.status_code == 401

    def test_unknown_task_is_404(self, client):
        res = client.post("/api/browser/does-not-exist/session", headers=ADMIN_HEADERS)
        assert res.status_code == 404

    def test_returns_503_when_assemblyai_is_unconfigured(self, client):
        """Failing loudly beats handing the browser a session it can't open."""
        task_id = _start(client)
        res = client.post(f"/api/browser/{task_id}/session", headers=ADMIN_HEADERS)
        assert res.status_code == 503
        assert res.json()["detail"] == "assemblyai_not_configured"


class TestBrowserTools:
    def test_tools_run_against_the_real_session(self, client):
        """The browser relays tool calls here rather than answering them, so an
        offer logged in a browser call lands on the negotiation just as it
        would on a phone call."""
        task_id = _start(client)

        res = client.post(
            f"/api/browser/{task_id}/tool",
            headers=ADMIN_HEADERS,
            json={
                "name": "log_offer",
                "arguments": {"monthly_rate": 64.99, "description": "12mo promo", "accepted": True},
            },
        )
        assert res.status_code == 200
        assert "logged" in res.json()["result"].lower()

        session = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
        assert session["offers"][0]["monthly_rate"] == 64.99
        assert session["offers"][0]["accepted"] is True

    def test_confirmation_number_reaches_the_session(self, client):
        task_id = _start(client)
        client.post(
            f"/api/browser/{task_id}/tool",
            headers=ADMIN_HEADERS,
            json={
                "name": "record_confirmation_number",
                "arguments": {"confirmation_number": "CMC-44192", "new_monthly_rate": 64.99},
            },
        )
        session = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
        assert session["confirmation_number"] == "CMC-44192"
        assert session["new_rate"] == 64.99

    def test_press_keys_says_there_is_no_keypad(self, client):
        """There is no phone line here. Telling the agent plainly beats letting
        it believe it navigated a menu that never existed."""
        task_id = _start(client)
        res = client.post(
            f"/api/browser/{task_id}/tool",
            headers=ADMIN_HEADERS,
            json={"name": "press_keys", "arguments": {"keys": "2"}},
        )
        assert "no phone keypad" in res.json()["result"]

    def test_requires_the_admin_key(self, client):
        res = client.post("/api/browser/some-task/tool", json={"name": "log_offer"})
        assert res.status_code == 401


class TestBrowserTranscript:
    def test_turns_reach_the_shared_event_feed(self, client):
        from app.services import events

        task_id = _start(client)
        client.post(
            f"/api/browser/{task_id}/transcript",
            headers=ADMIN_HEADERS,
            json={"speaker": "rep", "text": "Thanks for calling, this is Dana."},
        )
        feed = events.history(task_id)
        assert any(
            e.get("type") == "turn" and e.get("text") == "Thanks for calling, this is Dana."
            for e in feed
        )
        events.clear(task_id)

    def test_blank_turns_are_ignored(self, client):
        from app.services import events

        task_id = _start(client)
        client.post(
            f"/api/browser/{task_id}/transcript",
            headers=ADMIN_HEADERS,
            json={"speaker": "orion", "text": "   "},
        )
        assert not any(e.get("type") == "turn" for e in events.history(task_id))
        events.clear(task_id)


class TestLanguage:
    """Universal-3.5 Pro transcribes 18 languages natively, so the transcription
    half of a multilingual call is free. The parts that are not free are the
    voice and telling the agent what to speak."""

    def test_english_calls_use_the_default_voice(self):
        from app.services.languages import voice_for

        assert voice_for("en", "anna") == "anna"

    def test_other_languages_get_a_native_voice(self):
        from app.services.languages import voice_for

        assert voice_for("es", "anna") == "lola"
        assert voice_for("fr", "anna") == "estelle"

    def test_an_unknown_language_falls_back_rather_than_guessing(self):
        """An invented voice id is rejected outright at session.update, which
        would fail the call rather than degrade it."""
        from app.services.languages import voice_for

        assert voice_for("xx", "anna") == "anna"

    def test_english_adds_no_language_instruction(self):
        from app.services.languages import instruction_for

        assert instruction_for("en") == ""

    def test_other_languages_are_stated_explicitly(self):
        from app.services.languages import instruction_for

        instruction = instruction_for("es")
        assert "Spanish" in instruction
        # A model given an English prompt answers in English however well it
        # understood the question.
        assert "from your first word" in instruction

    def test_reference_numbers_are_not_translated(self):
        from app.services.languages import instruction_for

        assert "rather than translating" in instruction_for("de")


class TestTacticReading:
    def test_a_short_utterance_carries_no_stance(self):
        """"One moment" is not a position, and classifying it would spend a
        request to learn nothing."""
        import asyncio

        from app.services import tactics

        assert asyncio.run(tactics.read_stance("one sec")) is None

    def test_the_coaching_note_names_the_stance_and_the_move(self):
        from app.services import tactics

        note = tactics.coaching_note(
            {"stance": "softening", "has_authority": True, "advice": "Name your figure now."}
        )
        assert "softening" in note
        assert "Name your figure now." in note

    def test_a_powerless_rep_is_flagged_for_escalation(self):
        from app.services import tactics

        note = tactics.coaching_note(
            {"stance": "gatekeeping", "has_authority": False, "advice": "Ask for retention."}
        )
        assert "cannot approve this themselves" in note

    def test_every_stance_has_fallback_advice(self):
        """The classifier can return a stance without advice; the agent still
        needs to be told what to do about it."""
        from app.services import tactics

        assert set(tactics.FALLBACK_ADVICE) == set(tactics.STANCES)


class TestReceipts:
    """A receipt is public by design, so what it omits matters more than what
    it shows."""

    def test_an_unverified_negotiation_has_nothing_to_prove(self, client):
        task_id = _start(client)
        assert client.get(f"/api/receipts/{task_id}").status_code == 404

    def test_a_verified_saving_is_public_and_thin(self, client):
        task_id = _start(client)
        client.post(
            f"/api/negotiations/{task_id}/complete",
            headers=ADMIN_HEADERS,
            json={
                "outcome": "Rate reduced for 12 months.",
                "previous_rate": 89.99,
                "new_rate": 59.99,
                "confirmation_number": "CMC-44192",
            },
        )

        # No admin key: this is the point of a shareable link.
        res = client.get(f"/api/receipts/{task_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["monthly_saving"] == 30.0
        assert body["annual_saving"] == 360.0
        assert body["confirmation_number"] == "CMC-44192"

        # A link forwarded to a friend must not expose the account.
        for leak in ("phone_number", "account_details", "task_id", "bill"):
            assert leak not in body

    def test_unknown_task_is_404(self, client):
        assert client.get("/api/receipts/does-not-exist").status_code == 404


class TestRenewals:
    """A negotiated rate expires. The month before it does is when calling
    again is worth something."""

    def _with_contract_end(self, client, end_date: str) -> str:
        return client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Comcast",
                "phone_number": "+15551234567",
                "vertical": "cable_internet",
                "bill": {"provider": "Comcast", "contract_end_date": end_date},
            },
        ).json()["task_id"]

    def test_requires_the_admin_key(self, client):
        assert client.get("/api/renewals").status_code == 401

    def test_an_imminent_expiry_is_listed(self, client):
        from datetime import date, timedelta

        soon = (date.today() + timedelta(days=10)).isoformat()
        task_id = self._with_contract_end(client, soon)

        rows = client.get("/api/renewals", headers=ADMIN_HEADERS).json()
        assert any(r["task_id"] == task_id and r["days_remaining"] == 10 for r in rows)

    def test_a_distant_expiry_is_not_nagged_about(self, client):
        from datetime import date, timedelta

        far = (date.today() + timedelta(days=400)).isoformat()
        task_id = self._with_contract_end(client, far)
        rows = client.get("/api/renewals", headers=ADMIN_HEADERS).json()
        assert all(r["task_id"] != task_id for r in rows)

    def test_an_unparseable_date_is_skipped_not_fatal(self, client):
        """Bills print dates in whatever format they like; one odd bill must not
        break the whole listing."""
        self._with_contract_end(client, "sometime next spring")
        assert client.get("/api/renewals", headers=ADMIN_HEADERS).status_code == 200

    def test_already_expired_sorts_first(self, client):
        from datetime import date, timedelta

        self._with_contract_end(client, (date.today() + timedelta(days=30)).isoformat())
        self._with_contract_end(client, (date.today() - timedelta(days=5)).isoformat())

        rows = client.get("/api/renewals", headers=ADMIN_HEADERS).json()
        assert rows[0]["days_remaining"] < rows[-1]["days_remaining"]


class TestEscalationNotifications:
    def test_no_configured_channel_is_reported_honestly(self, client):
        """Better the agent asks for a callback number than promises a rescue
        that isn't coming."""
        task_id = _start(client)
        res = client.post(
            f"/api/browser/{task_id}/tool",
            headers=ADMIN_HEADERS,
            json={"name": "escalate_to_human", "arguments": {"reason": "Rep refused"}},
        )
        result = res.json()["result"]
        assert "No one could be reached" in result
        assert "callback number" in result

    def test_the_session_still_records_the_escalation(self, client):
        task_id = _start(client)
        client.post(
            f"/api/browser/{task_id}/tool",
            headers=ADMIN_HEADERS,
            json={"name": "escalate_to_human", "arguments": {"reason": "Rep refused"}},
        )
        session = client.get(f"/api/negotiations/{task_id}", headers=ADMIN_HEADERS).json()
        assert session["escalated"] is True
        assert session["escalation_reason"] == "Rep refused"


class TestSilencePolicy:
    """The bug this exists for: the API waits for a user utterance, so if
    nobody answers after the greeting, no turn ever ends and the agent sits
    silent for the whole call. A person checks you're still there, tries once
    more, then hangs up."""

    def test_there_are_three_escalating_prompts(self):
        from app.services.voice_agent import SILENCE_PROMPTS

        assert len(SILENCE_PROMPTS) == 3
        delays = [d for d, _ in SILENCE_PROMPTS]
        assert delays == sorted(delays), "waits should lengthen, not shorten"

    def test_the_first_prompt_checks_they_are_there(self):
        from app.services.voice_agent import SILENCE_PROMPTS

        assert "still there" in SILENCE_PROMPTS[0][1].lower()

    def test_the_last_prompt_says_goodbye(self):
        """Idle time on an open session is billed, so an unanswered call has to
        end rather than sit there costing money."""
        from app.services.voice_agent import SILENCE_PROMPTS

        assert "goodbye" in SILENCE_PROMPTS[-1][1].lower()

    def test_prompts_ask_for_one_short_line(self):
        """A nudge that turns into a speech is worse than the silence."""
        from app.services.voice_agent import SILENCE_PROMPTS

        for _, instructions in SILENCE_PROMPTS:
            assert "one short line" in instructions.lower()

    def test_speaking_resets_the_ladder_rather_than_escalating(self):
        """Someone who answers the second prompt must not then be hung up on."""
        import asyncio

        from app.services.voice_agent import SILENCE_PROMPTS, VoiceAgentRelay

        class Relay(VoiceAgentRelay):
            def __init__(self):
                super().__init__(None, label="test")
                self.prompts = 0

            def session_config(self):
                return {}

            async def prompt_reply(self, instructions=None):
                self.prompts += 1
                # Answer the first nudge, as a real person would.
                if self.prompts == 1:
                    self._heard_something.set()

        async def run():
            relay = Relay()
            # Shrink the waits so the test doesn't sit for 30 seconds.
            import app.services.voice_agent as va

            original = va.SILENCE_PROMPTS
            va.SILENCE_PROMPTS = tuple((0.01, text) for _, text in original)
            try:
                await asyncio.wait_for(relay._watch_for_silence(), timeout=5)
            finally:
                va.SILENCE_PROMPTS = original
            return relay

        relay = asyncio.run(run())
        # Answering restarts the ladder, so it takes more than three prompts to
        # reach the end - it never simply marched to a hang-up.
        assert relay.prompts > len(SILENCE_PROMPTS)
        assert relay._give_up.is_set()


class TestLanguageReachesTheSession:
    """The end-to-end check the isolated unit tests missed.

    voice_for() and instruction_for() were both correct and both tested, but
    StartNegotiationRequest had no `language` field - so Pydantic dropped it
    silently and every call defaulted to English. The feature was wired
    everywhere except where the choice arrives.
    """

    def _start(self, client, language: str) -> dict:
        return client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={
                "provider": "Movistar",
                "phone_number": "+34911111111",
                "vertical": "cable_internet",
                "language": language,
            },
        ).json()

    def test_the_chosen_language_is_stored(self, client):
        assert self._start(client, "es")["language"] == "es"

    def test_it_defaults_to_english_when_unspecified(self, client):
        res = client.post(
            "/api/negotiations/start",
            headers=ADMIN_HEADERS,
            json={"provider": "Comcast", "phone_number": "+15551234567", "vertical": "cable_internet"},
        )
        assert res.json()["language"] == "en"

    def test_the_prompt_actually_tells_the_agent_to_speak_it(self, client):
        """This is the assertion that would have caught the bug: not that the
        helper works, but that the language survives the round trip into the
        prompt the agent is given."""
        import asyncio

        from app.services import prompting
        from app.store import get_session

        task_id = self._start(client, "es")["task_id"]
        session = asyncio.run(get_session(task_id))
        assert session is not None
        assert "Spanish" in prompting.system_instruction(session)

    def test_the_voice_matches_the_language(self, client):
        import asyncio

        from app.services.languages import voice_for
        from app.store import get_session

        task_id = self._start(client, "fr")["task_id"]
        session = asyncio.run(get_session(task_id))
        assert voice_for(session.language, "anna") == "estelle"
