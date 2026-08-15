"""Produces the Embeddings object used to vectorise company knowledge chunks."""

from langchain_core.embeddings import Embeddings

from backend.config.settings import settings
from backend.utils.logger import logger


def get_embeddings() -> Embeddings:
    """Return an Embeddings implementation compatible with Qdrant.

    Uses Google Gemini embeddings when a Gemini/Google API key is configured
    (best quality). Falls back to a local HuggingFace sentence-transformers
    model so the pipeline still runs (e.g. in demos/tests) without any
    embedding API key.
    """
    if settings.google_api_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        logger.info(f"Using GoogleGenerativeAIEmbeddings ({settings.GEMINI_EMBEDDING_MODEL})")
        return GoogleGenerativeAIEmbeddings(
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.google_api_key,
        )

    logger.warning(
        "GEMINI_API_KEY/GOOGLE_API_KEY not set — falling back to local HuggingFace embeddings"
    )
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name=settings.FASTEMBED_MODEL)
