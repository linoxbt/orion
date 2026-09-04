from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    assemblyai_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    stripe_secret_key: str = ""

    # Paystack takes the upgrade payment. Stripe does not support Nigerian
    # merchants, so a Nigerian business cannot hold a Stripe account; Paystack
    # is Stripe-owned and covers Nigeria, Ghana, Kenya, South Africa and Cote
    # d'Ivoire.
    paystack_secret_key: str = ""
    paystack_currency: str = "NGN"

    # Which methods the checkout offers, in order. Card is listed first even
    # though a new Paystack account usually cannot take cards yet: Paystack
    # ignores a channel the account has not been approved for, so listing it
    # costs nothing now and makes card appear the moment it is enabled,
    # without a deploy. Every channel being inactive is what fails, so keep at
    # least one the account actually has.
    paystack_channels: str = "card,bank,ussd,bank_transfer"
    # What the upgrade costs, in whole units of paystack_currency. NGN is the
    # default because a Nigerian Paystack account settles in naira; set both
    # together when charging in another currency.
    pro_price: int = 22500
    base_url: str = "http://localhost:8080"

    # CORS: comma-separated list of origins allowed to call this API from a
    # browser. Defaults to the frontend's local dev origin only - set this to
    # the real deployed frontend URL(s) in production (main.py's CORS
    # middleware previously defaulted to allow_origins=["*"], which the
    # architecture doc's "don't ship the dev-convenience default" guidance
    # calls out as something to fix before production).
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    # Gates POST /api/negotiations/start and /charge (see app/security.py).
    # Unset by default = those endpoints reject every request rather than
    # being silently wide open - the architecture doc calls out an
    # unauthenticated "place a call" endpoint as a real, billable footgun.
    # Dynamic's environment id, used to fetch the JWKS that session tokens are
    # verified against. Unset means the backend cannot verify a session and
    # falls back to trusting the proxy's header - see app/security.py.
    dynamic_environment_id: str = ""

    admin_api_key: str = ""

    # Fernet key encrypting the account-verification details a customer
    # supplies (account number, security PIN, last-4 SSN). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Unset means the vault refuses to store anything rather than falling back
    # to plaintext, so a call simply can't answer verification questions.
    # Supabase - profiles and negotiations. The service key bypasses RLS, which
    # is the point: identity comes from Dynamic, so auth.uid() is null in that
    # database and the tables are deny-all by design.
    supabase_url: str = ""
    supabase_service_key: str = ""

    account_encryption_key: str = ""

    # Reaching the customer when the agent escalates mid-call. All optional -
    # an unconfigured channel is skipped, never an error, because a failed
    # notification must not take down a live phone call.
    twilio_whatsapp_from: str = ""      # the WhatsApp-enabled Twilio number
    escalation_whatsapp_to: str = ""    # the customer's WhatsApp number, E.164
    sendgrid_api_key: str = ""
    escalation_email_to: str = ""
    escalation_email_from: str = ""
    # Used to build a link back into the app in the notification body.
    public_app_url: str = ""

    # SQLite file backing app/store.py - interim persistence until a GCP
    # project exists for real Firestore (architecture doc Section 2/6).
    database_path: str = "orion.db"

    # Model IDs churn - verify against ai.google.dev before each deploy
    # (architecture doc Section 2). The original defaults here
    # (gemini-2.5-flash, gemini-live-2.5-flash-preview) went stale within
    # weeks - gemini-2.5-flash now 404s for new API keys ("no longer
    # available to new users"). Re-verified live against the real API on
    # 2026-08-09: gemini-flash-latest resolves to a current model and
    # gemini-3.1-flash-live-preview is confirmed to support the Live API
    # (bidiGenerateContent). Using the "-latest" alias for the non-live
    # model specifically to avoid re-going-stale the same way.
    # Ordered fallback, not a single pin. A model can be saturated for minutes
    # at a time - "This model is currently experiencing high demand" - and
    # retrying the same one is futile, which is exactly how extraction kept
    # failing. Verified reachable on 2026-09-03; gemini-flash-latest was 503 on
    # every attempt while all three of these answered.
    gemini_models: str = "gemini-3.5-flash,gemini-flash-lite-latest,gemini-3.1-flash-lite-preview"

    @property
    def gemini_model_chain(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @property
    def gemini_model(self) -> str:
        """The first choice, for callers that only need one."""
        return self.gemini_model_chain[0]
    # Retained for the pre-AssemblyAI Gemini Live bridge, kept in git history
    # only - nothing on the call path reads this any more.
    gemini_live_model: str = "gemini-3.1-flash-live-preview"

    # Which implementation holds the live call (see app/services/live_bridge.py):
    #   "agent_api"  - AssemblyAI Voice Agent API: STT + LLM + TTS + turn
    #                  detection + tool calling over one websocket, mu-law in
    #                  and out so Twilio audio passes through untranscoded.
    #   "stt_gemini" - AssemblyAI Universal-3.5 Pro streaming STT -> AssemblyAI
    #                  LLM Gateway (Gemini) -> Google Cloud TTS, with this app
    #                  owning the turn loop.
    voice_backend: str = "agent_api"

    # Voice Agent API voice id. The catalog is live (GET /v1/voices) and grows -
    # an invented id is rejected outright at session.update, so change this
    # only to something that endpoint actually returns.
    assemblyai_voice: str = "anna"

    # LLM Gateway model id. Exact versioned strings only - a bare family name
    # ("gemini-flash") is invalid.
    #
    # Access is per-account, not just per-id: a current, correctly-spelled model
    # still returns 400 "Your account does not have access to this LLM Gateway
    # model" if the account isn't entitled to it. As of 2026-09-02 this key
    # reaches only AssemblyAI's own qwen3.5-4b-32k-fast, so that's the default -
    # it's used for the structured jobs (outcome extraction, turn
    # classification), which a 4B model handles fine. Add billing to the
    # AssemblyAI account to unlock gemini-3.6-flash and the Claude models.
    llm_gateway_model: str = "qwen3.5-4b-32k-fast"

    # Which provider runs the negotiation itself on the stt_gemini backend:
    #   "gemini_direct" - google-genai with GEMINI_API_KEY. The default, because
    #                     holding a multi-round negotiation needs a stronger
    #                     model than LLM Gateway currently grants this account.
    #   "llm_gateway"   - AssemblyAI LLM Gateway, using llm_gateway_model above.
    #                     Switch to this once the account can reach a capable
    #                     model; nothing else needs to change.
    negotiation_llm: str = "gemini_direct"


settings = Settings()
