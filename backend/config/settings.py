from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so imports work from the repo root
# (python backend/test_pipeline.py) and from inside backend/ alike.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # --- LLM (Google Gemini) ---
    # GEMINI_API_KEY is the primary name; GOOGLE_API_KEY is accepted too
    # since that's the env var the Google SDKs look for by convention.
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_MAX_TOKENS: int = 4096

    # --- Embeddings ---
    # Gemini embeddings are used when a Gemini/Google API key is set;
    # otherwise the local HuggingFace model below is used so the pipeline
    # runs without any embedding API key.
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    FASTEMBED_MODEL: str = "BAAI/bge-small-en-v1.5"

    # --- Search / enrichment ---
    TAVILY_API_KEY: str = ""
    SERPER_API_KEY: str = ""
    APOLLO_API_KEY: str = ""
    HUNTER_API_KEY: str = ""

    # --- Vector store ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # --- Infra ---
    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = ""

    # --- RAG tuning ---
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    RETRIEVER_TOP_K: int = 5

    # --- Pipeline tuning ---
    MAX_LEADS_TO_RESEARCH: int = 10
    MIN_QUALIFICATION_SCORE: int = 40
    SENDER_COMPANY_NAME: str = "Our Company"
    CALENDAR_BASE_URL: str = "https://cal.com/admin"

    model_config = SettingsConfigDict(
        env_file=(_ROOT_DIR / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def google_api_key(self) -> str:
        """Effective Gemini/Google API key — GEMINI_API_KEY takes precedence
        over GOOGLE_API_KEY when both are set."""
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY


settings = Settings()
