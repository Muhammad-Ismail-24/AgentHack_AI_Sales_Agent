"""Ingests the company PDF/text into Qdrant so downstream agents can query it."""

from rag.chunker import chunk_text
from rag.document_loader import load_from_pdf, load_from_text
from rag.vector_store import QdrantVectorStore
from utils.logger import logger


def _guess_company_name(first_chunk: str) -> str:
    """Best-effort company name from the first chunk of the ingested document."""
    if not first_chunk:
        return "the company"
    for line in first_chunk.splitlines():
        line = line.strip(" \t-#*")
        if line:
            return line[:80]
    return "the company"


async def run(state: dict) -> dict:
    """Load state['raw_input'] (filepath or text) per state['input_type'],
    chunk it, and upsert into Qdrant collection 'company_{session_id}'.

    Sets state['company_collection'] and state['company_name'].
    """
    try:
        session_id = state.get("session_id", "unknown")
        raw_input = state.get("raw_input", "")
        input_type = state.get("input_type", "text")

        if input_type == "pdf":
            text = load_from_pdf(raw_input)
        else:
            text = load_from_text(raw_input)

        if not text:
            logger.error("rag_agent: no text could be loaded from raw_input")
            return state

        chunks = chunk_text(text)
        if not chunks:
            logger.error("rag_agent: chunking produced no chunks")
            return state

        collection_name = f"company_{session_id}"
        store = QdrantVectorStore()
        store.upsert(chunks, collection_name)

        state["company_collection"] = collection_name
        state["company_name"] = _guess_company_name(chunks[0])
        logger.info(
            f"rag_agent: ingested {len(chunks)} chunks into '{collection_name}' "
            f"(company_name='{state['company_name']}')"
        )
        return state
    except Exception as e:
        logger.error(f"rag_agent failed: {e}")
        return state
