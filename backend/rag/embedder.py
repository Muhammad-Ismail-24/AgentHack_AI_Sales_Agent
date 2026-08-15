"""Produces the Embeddings object used to vectorise company knowledge chunks."""

from langchain_core.embeddings import Embeddings

from config.settings import settings
from utils.logger import logger

# Cached for the life of the process — mirrors llm_utils._llm's caching so we
# only pay the probe-call cost once, not on every rag_agent/retriever call.
_embeddings: Embeddings | None = None


def _local_embeddings() -> Embeddings:
    # FastEmbedEmbeddings (ONNX-based, no PyTorch) matches the FASTEMBED_MODEL
    # setting name and is far lighter than sentence-transformers for a Render
    # instance this size.
    from langchain_community.embeddings import FastEmbedEmbeddings

    return FastEmbedEmbeddings(model_name=settings.FASTEMBED_MODEL)


def get_embeddings() -> Embeddings:
    """Return an Embeddings implementation compatible with Qdrant.

    Uses Google Gemini embeddings when a Gemini/Google API key is configured
    (best quality). Google periodically retires embedding model names (the
    same way it retires chat models — see llm_utils._switch_to_fallback), and
    an embedding call against a retired model 404s. Rather than let every
    rag_agent upsert fail silently, this probes the configured model once and
    falls back to a local FastEmbed (ONNX) model — the same fallback already
    used when no embedding API key is configured at all.
    """
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    if settings.google_api_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        candidate = GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.google_api_key,
        )
        try:
            candidate.embed_query("healthcheck")
        except Exception as exc:  # noqa: BLE001 - any failure means "use the fallback"
            logger.warning(
                "Gemini embedding model %r failed a health check (%s) — "
                "falling back to local FastEmbed embeddings.",
                settings.GEMINI_EMBEDDING_MODEL, exc,
            )
        else:
            logger.info(f"Using GoogleGenerativeAIEmbeddings ({settings.GEMINI_EMBEDDING_MODEL})")
            _embeddings = candidate
            return _embeddings
    else:
        logger.warning(
            "GEMINI_API_KEY/GOOGLE_API_KEY not set — falling back to local FastEmbed embeddings"
        )

    _embeddings = _local_embeddings()
    return _embeddings
