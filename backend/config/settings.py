"""Central settings object. Every env var the backend reads is declared here.

Merged from all three branches: Wajeeh's infra keys, Ismail's Gemini/RAG
tuning, and Sufiyan's comms keys. Import the singleton, never os.getenv:

    from config.settings import settings
    settings.google_api_key
"""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root — backend/config/settings.py -> backend/ -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """All configuration, loaded from the environment or a .env file.

    Every key is optional with a safe default so the app still boots (and
    /health still answers) when a provider key is missing. Modules that
    genuinely need a key check for it at call time.
    """

    model_config = SettingsConfigDict(
        # `env` (no dot) is the filename the key file actually ships as.
        env_file=(
            REPO_ROOT / ".env",
            REPO_ROOT / "env",
            BASE_DIR / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ── LLM (Google Gemini) ──────────────────────────────────────────
    # GEMINI_API_KEY is primary; GOOGLE_API_KEY is what the Google SDKs
    # look for by convention. Either works — read `google_api_key`.
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    # Used automatically if GEMINI_MODEL has been retired. `-latest` aliases
    # track the current release, so this keeps working without a code change.
    GEMINI_FALLBACK_MODEL: str = "gemini-flash-latest"
    # Tried in order, after GEMINI_MODEL and GEMINI_FALLBACK_MODEL, when a
    # model is out of quota or has been retired. The free-tier request cap is
    # per project *per model* (the 429 names it
    # GenerateRequestsPerDayPerProjectPerModel-FreeTier), so each entry here
    # carries its own daily budget and a spent model does not stop the run.
    # `-lite` models are listed first because their free-tier caps are the
    # most generous. Comma-separated; blank disables chaining.
    GEMINI_MODEL_FALLBACKS: str = (
        "gemini-3.5-flash-lite,gemini-flash-lite-latest,"
        "gemini-3.6-flash,gemini-3.7-flash"
    )

    @property
    def gemini_model_chain(self) -> list[str]:
        """Every model to try, in order, deduplicated and blank-free."""
        names = [self.GEMINI_MODEL, self.GEMINI_FALLBACK_MODEL]
        names += self.GEMINI_MODEL_FALLBACKS.split(",")
        chain: list[str] = []
        for name in names:
            cleaned = (name or "").strip()
            if cleaned and cleaned not in chain:
                chain.append(cleaned)
        return chain
    GEMINI_MAX_TOKENS: int = 4096
    # Free-tier budget is 15 requests/minute across everything sharing the
    # key. The limiter in agents/llm_utils.py holds calls to this many per
    # rolling 60s (14 leaves one request of headroom). Raise on a paid tier.
    GEMINI_RPM: int = 14
    # How many times a single call waits out a 429 before giving up with
    # GeminiQuotaExhausted (0 = fail on the first 429).
    GEMINI_429_RETRIES: int = 2

    # ── LLM: Groq — the intelligence layer only ──────────────────────
    # Devil's Advocate, Deal Autopsy and the Executive Whisperer script.
    # A separate key from Gemini on purpose: those features are
    # interactive, and the Gemini free tier is capped per day per model —
    # sharing one key would let a demo exhaust the pipeline's budget.
    # Nothing reads these yet; the features are not built.
    GROQ_API_KEY: str = ""

    # ── Text-to-speech: drive-time audio briefing (optional) ─────────
    # Without a key the pre-call script is still written and still sent as
    # text; only the WhatsApp voice note is skipped. Not read yet either.
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"
    ELEVENLABS_MODEL_ID: str = "eleven_turbo_v2_5"

    # ── Embeddings ───────────────────────────────────────────────────
    # text-embedding-004 was retired — it 404s on embedContent, which made
    # rag/embedder.py fail its health check on every boot and fall back to
    # downloading the local FastEmbed model. gemini-embedding-001 is the
    # current one (3072 dims). Collections are per-session, so a dimension
    # change never clashes with an existing one.
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    FASTEMBED_MODEL: str = "BAAI/bge-small-en-v1.5"

    # ── Web search / research ────────────────────────────────────────
    TAVILY_API_KEY: str = ""
    SERPER_API_KEY: str = ""

    # ── Contact enrichment ───────────────────────────────────────────
    APOLLO_API_KEY: str = ""
    HUNTER_API_KEY: str = ""

    # ── Vector store ─────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "company_knowledge"

    # ── Cache / short-term memory ────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Database (Firestore) ─────────────────────────────────────────
    # Path to the Firebase service-account JSON. When empty, the app falls
    # back to Application Default Credentials, then to the Firestore
    # emulator if FIRESTORE_EMULATOR_HOST is set.
    FIREBASE_SERVICE_ACCOUNT_PATH: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIRESTORE_EMULATOR_HOST: str = ""

    # Retained so a Postgres URL in the env file does not fail validation.
    # Nothing reads it any more — persistence is Firestore.
    DATABASE_URL: str = ""

    # ── Email: SMTP is the active path ───────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    # Resend is kept as an optional alternative sender.
    RESEND_API_KEY: str = ""
    SENDER_EMAIL: str = ""
    # When set, every outreach email goes here instead of the prospect, with
    # a banner naming who it would have reached. For rehearsing the full
    # loop — send, reply, classify, book — without cold-emailing anyone, and
    # for Resend accounts with no verified domain, which may only deliver to
    # the account holder. Leave blank in real use. The subject is left
    # untouched on purpose: EmailReader matches a reply to its original by
    # subject, so changing it would break the reply half of the round trip.
    TEST_RECIPIENT_EMAIL: str = ""

    # ── Meetings ─────────────────────────────────────────────────────
    # CAL_API_KEY is the name in the env file; CALCOM_API_KEY is the older
    # name some modules used. Read `cal_api_key`.
    CAL_API_KEY: str = ""
    CALCOM_API_KEY: str = ""
    CALENDAR_BASE_URL: str = "https://cal.com/admin"
    # Your real, public booking page — the one a prospect can actually open.
    # Cal.com, Calendly or a Google Calendar appointment schedule all work;
    # paste the link exactly as the provider gives it, e.g.
    # https://cal.com/your-name/30min. This is what goes in every outreach
    # email and every meeting-link reply. Leave it blank and the old
    # per-company path is generated instead, which 404s.
    CALENDAR_BOOKING_URL: str = ""

    # ── WhatsApp: Green API is the active path ────────────────────────
    # Simple REST API — {GREEN_API_URL}/waInstance{id}/sendMessage/{token}.
    # No SDK, just POSTs. See comms/whatsapp_notifier.py.
    GREEN_API_URL: str = "https://api.greenapi.com"
    GREEN_API_ID_INSTANCE: str = ""
    GREEN_API_TOKEN_INSTANCE: str = ""
    ADMIN_WHATSAPP_NUMBER: str = ""

    # ── WhatsApp (Twilio) — legacy fallback, skipped unless configured ─
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""

    # ── RAG tuning (Ismail) ──────────────────────────────────────────
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    RETRIEVER_TOP_K: int = 5

    # ── Pipeline tuning (Ismail) ─────────────────────────────────────
    # Each researched lead costs 1 LLM call in combined_processing (which
    # merged the old qualification/service_match/decision_maker/email_writer
    # calls into one). A full run is therefore icp(1) + filter(1 per 15 raw
    # leads) + this many — 9 calls at 6 leads, inside a 15 RPM budget.
    MAX_LEADS_TO_RESEARCH: int = 6
    MIN_QUALIFICATION_SCORE: int = 40
    SENDER_COMPANY_NAME: str = "NovaTech Solutions"

    # ── App behaviour ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: Path = REPO_ROOT / "data" / "uploads"
    SEED_DIR: Path = REPO_ROOT / "data" / "seeds"
    FOLLOWUP_AFTER_DAYS: int = 3
    PIPELINE_STATE_TTL_SECONDS: int = 60 * 60 * 2  # 2 hours

    # ── Normalisers ──────────────────────────────────────────────────

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def _normalise_redis_url(cls, value: object) -> str:
        """Coerce whatever the Redis dashboard gave you into a usable URL.

        Handles three shapes people actually paste:
          * a full `redis://` / `rediss://` URL — used as-is;
          * a bare `host:port` — gets a scheme;
          * an entire `redis-cli --tls -u redis://...` command line — the URL
            is extracted out of it.

        redis-py rejects anything else outright, and a bad cache URL should
        never be the thing that stops the app booting.
        """
        import re

        raw = str(value or "").strip()
        if not raw:
            return "redis://localhost:6379/0"

        # A pasted command line: pull the first redis:// or rediss:// token.
        match = re.search(r"rediss?://\S+", raw)
        if match:
            url = match.group(0)
            # `redis-cli --tls -u redis://...` means TLS is required even
            # though the URL says otherwise. Managed Redis (Upstash, Redis
            # Cloud) closes the connection outright without it.
            if "--tls" in raw and url.startswith("redis://"):
                url = url.replace("redis://", "rediss://", 1)
            return url

        if "://" in raw:
            return raw

        # Bare host:port, possibly still wrapped in CLI flags.
        token = next(
            (
                part
                for part in raw.split()
                if ":" in part and not part.startswith("-")
            ),
            None,
        )
        return f"redis://{token or raw}"

    @field_validator("QDRANT_URL", mode="before")
    @classmethod
    def _normalise_qdrant_url(cls, value: object) -> str:
        url = str(value or "").strip()
        if not url:
            return "http://localhost:6333"
        if "://" in url:
            return url
        return f"https://{url}"

    @field_validator("GEMINI_MODEL", "CALENDAR_BASE_URL", mode="before")
    @classmethod
    def _fall_back_when_blank(cls, value: object, info) -> object:
        """An empty value in the env file must not beat the default."""
        if value is None or (isinstance(value, str) and not value.strip()):
            field = cls.model_fields[info.field_name]
            return field.default
        return value

    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def _default_smtp_port(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 587
        return value

    # ── Effective-value helpers ──────────────────────────────────────

    @property
    def google_api_key(self) -> str:
        """GEMINI_API_KEY wins over GOOGLE_API_KEY when both are set."""
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY

    @property
    def cal_api_key(self) -> str:
        return self.CAL_API_KEY or self.CALCOM_API_KEY

    @property
    def sender_email(self) -> str:
        """The From address to send as.

        When SMTP is the transport the From must be the authenticated
        mailbox — Gmail rewrites or rejects anything else, and a leftover
        `onboarding@resend.dev` from the Resend setup would silently break
        deliverability. So SMTP_USER wins whenever SMTP is configured, and
        SENDER_EMAIL is only used for the Resend path.
        """
        if self.smtp_configured:
            return self.SMTP_USER or self.SENDER_EMAIL
        return self.SENDER_EMAIL or self.SMTP_USER

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
