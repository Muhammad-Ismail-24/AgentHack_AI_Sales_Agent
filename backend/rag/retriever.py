"""Query interface used by all agents to pull grounded company knowledge from Qdrant."""

from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore as LCQdrantVectorStore

from config.settings import settings
from rag.embedder import get_embeddings
from rag.vector_store import QdrantVectorStore
from utils.logger import logger


def get_retriever(collection: str, k: int = None) -> VectorStoreRetriever | None:
    """Return a VectorStoreRetriever bound to the given Qdrant collection."""
    try:
        store = QdrantVectorStore()
        if not store.collection_exists(collection):
            logger.warning(f"Collection '{collection}' does not exist")
            return None

        lc_store = LCQdrantVectorStore(
            client=store.client,
            collection_name=collection,
            embedding=get_embeddings(),
        )
        return lc_store.as_retriever(
            search_kwargs={"k": k or settings.RETRIEVER_TOP_K}
        )
    except Exception as e:
        logger.error(f"Error building retriever for '{collection}': {e}")
        return None


def query(question: str, collection: str, k: int = 5) -> str:
    """Retrieve the top-k chunks for `question` and return them as one joined string."""
    try:
        retriever = get_retriever(collection, k=k)
        if retriever is None:
            return ""
        docs = retriever.invoke(question)
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as e:
        logger.error(f"Error querying collection '{collection}': {e}")
        return ""


if __name__ == "__main__":
    from rag.chunker import chunk_text
    from rag.document_loader import load_from_text

    test_collection = "test_company_knowledge"

    dummy_text = """
    Acme Logistics is a UAE-based logistics and freight forwarding company
    founded in 2015. We specialise in last-mile delivery automation for
    e-commerce businesses across the Middle East. Our core services include
    warehouse management, real-time shipment tracking, and WhatsApp-based
    customer notifications. We serve mid-sized retailers with 50-500
    employees who need to scale their delivery operations without building
    an in-house logistics team.
    """

    print("Loading dummy text...")
    text = load_from_text(dummy_text)

    print("Chunking...")
    chunks = chunk_text(text)
    print(f"Got {len(chunks)} chunks")

    print(f"Upserting into '{test_collection}'...")
    store = QdrantVectorStore()
    store.upsert(chunks, test_collection)

    print("Querying: 'what services does this company offer?'")
    result = query("what services does this company offer?", test_collection, k=3)
    print("--- Result ---")
    print(result)
