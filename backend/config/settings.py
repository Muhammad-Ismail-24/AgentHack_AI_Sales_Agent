"""Central settings object. Every env var the backend reads is declared here.

Import the singleton, never os.getenv directly:

    from config.settings import settings
    settings.ANTHROPIC_API_KEY
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
    /health still answers) when a teammate has not filled in every provider
    key yet. Modules that genuinely need a key check for it at call time.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ── LLM ──────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

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

    # ── Database ─────────────────────────────────────────────────────
    # asyncpg driver for the app, psycopg2 is derived from it for Alembic.
    DATABASE_URL: str = (
        "postgresql+asyncpg://admin:password@localhost:5432/agenthack"
    )

    # ── Email ────────────────────────────────────────────────────────
    RESEND_API_KEY: str = ""
    SENDER_EMAIL: str = ""

    # ── WhatsApp (Twilio) ────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    ADMIN_WHATSAPP_NUMBER: str = ""

    # ── Meetings ─────────────────────────────────────────────────────
    CALCOM_API_KEY: str = ""

    # ── App behaviour ────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: Path = REPO_ROOT / "data" / "uploads"
    SEED_DIR: Path = REPO_ROOT / "data" / "seeds"
    FOLLOWUP_AFTER_DAYS: int = 3
    PIPELINE_STATE_TTL_SECONDS: int = 60 * 60 * 2  # 2 hours

    @property
    def sync_database_url(self) -> str:
        """Same database, sync driver — used by Alembic and load_seeds.py."""
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite", 1)
        return url.replace("+asyncpg", "+psycopg2")

    @property
    def async_database_url(self) -> str:
        """Same database, guaranteed async driver."""
        url = self.DATABASE_URL
        if "+asyncpg" in url or url.startswith("sqlite+aiosqlite"):
            return url
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("+psycopg2", "+asyncpg")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
