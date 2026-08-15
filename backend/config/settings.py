"""Central settings object. Every env var the backend reads is declared here.

Merged from all three branches: Wajeeh's infra keys, Ismail's Gemini/RAG
tuning, and Sufiyan's comms keys. Import the singleton, never os.getenv:

    from config.settings import settings
    settings.google_api_key
"""

from functools import lru_cache
from pathlib import Path

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
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_MAX_TOKENS: int = 4096

    # ── Embeddings ───────────────────────────────────────────────────
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
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

    # ── Meetings ─────────────────────────────────────────────────────
    # CAL_API_KEY is the name in the env file; CALCOM_API_KEY is the older
    # name some modules used. Read `cal_api_key`.
    CAL_API_KEY: str = ""
    CALCOM_API_KEY: str = ""
    CALENDAR_BASE_URL: str = "https://cal.com/admin"

    # ── WhatsApp (Twilio) — skipped for now, kept so keys validate ────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    ADMIN_WHATSAPP_NUMBER: str = ""

    # ── RAG tuning (Ismail) ──────────────────────────────────────────
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    RETRIEVER_TOP_K: int = 5

    # ── Pipeline tuning (Ismail) ─────────────────────────────────────
    MAX_LEADS_TO_RESEARCH: int = 10
    MIN_QUALIFICATION_SCORE: int = 40
    SENDER_COMPANY_NAME: str = "NovaTech Solutions"

    # ── App behaviour ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: Path = REPO_ROOT / "data" / "uploads"
    SEED_DIR: Path = REPO_ROOT / "data" / "seeds"
    FOLLOWUP_AFTER_DAYS: int = 3
    PIPELINE_STATE_TTL_SECONDS: int = 60 * 60 * 2  # 2 hours

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
        """The From address — falls back to the SMTP account itself."""
        return self.SENDER_EMAIL or self.SMTP_USER

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
