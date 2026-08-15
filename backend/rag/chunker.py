"""Splits a document into overlapping chunks for embedding."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config.settings import settings
from backend.utils.logger import logger


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks using RecursiveCharacterTextSplitter.

    chunk_size=800, chunk_overlap=150 (see backend/config/settings.py).
    """
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    try:
        chunks = splitter.split_text(text)
        logger.info(f"Chunked text into {len(chunks)} chunks")
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        return []
