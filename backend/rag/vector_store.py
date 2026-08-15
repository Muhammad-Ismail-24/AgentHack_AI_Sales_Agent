"""Qdrant client wrapper — upsert company knowledge chunks and check collections."""

from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config.settings import settings
from rag.embedder import get_embeddings
from utils.logger import logger

_ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# Cache the underlying QdrantClient across QdrantVectorStore() instances.
# Important for the local on-disk fallback: qdrant-client's embedded/local
# mode locks its storage directory per open client, so re-opening a new
# client to the same path while another is still alive raises a "storage
# folder already accessed" error. Reusing one client per process avoids that.
_client_cache: dict[str, QdrantClient] = {}


class QdrantVectorStore:
    """Thin wrapper around the Qdrant client + LangChain's QdrantVectorStore.

    Connects to Qdrant using QDRANT_URL from settings and exposes the two
    operations every RAG agent needs: upsert(chunks, collection) and
    collection_exists(collection).
    """

    def __init__(self):
        self.client = self._get_client()
        self.embeddings = get_embeddings()

    @classmethod
    def _get_client(cls) -> QdrantClient:
        cache_key = settings.QDRANT_URL
        if cache_key not in _client_cache:
            _client_cache[cache_key] = cls._connect()
        return _client_cache[cache_key]

    @staticmethod
    def _connect() -> QdrantClient:
        """Connect to the configured Qdrant server; fall back to a local
        on-disk instance (no server required) if it's unreachable, so the
        pipeline stays runnable for local dev/demo without docker-compose.
        """
        try:
            client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=3,
            )
            client.get_collections()
            return client
        except Exception as e:
            logger.warning(
                f"Could not reach Qdrant at {settings.QDRANT_URL} ({e}); "
                "falling back to local on-disk Qdrant at data/cache/qdrant_local"
            )
            local_path = str(_ROOT_DIR / "data" / "cache" / "qdrant_local")
            return QdrantClient(path=local_path)

    def collection_exists(self, collection: str) -> bool:
        try:
            return self.client.collection_exists(collection_name=collection)
        except Exception as e:
            logger.error(f"Error checking collection '{collection}': {e}")
            return False

    def upsert(self, chunks: list[str], collection: str) -> None:
        """Embed and upsert a list of text chunks into the given collection.

        Creates the collection (sized to the embedding model's dimension) if
        it does not already exist, then appends the chunks to it.

        Note: the vector dimension is fixed at collection-creation time to
        whichever embedder was active then (Gemini's text-embedding-004 is
        768-dim; the local HuggingFace fallback is 384-dim). Since
        collections are per-session ('company_{session_id}'), a new session
        always gets a fresh collection sized to the current embedder — but
        re-upserting into an *existing* collection after switching embedding
        providers will raise a dimension-mismatch error from Qdrant.
        """
        if not chunks:
            logger.warning(f"No chunks to upsert into '{collection}'")
            return

        try:
            from langchain_qdrant import QdrantVectorStore as LCQdrantVectorStore

            if not self.collection_exists(collection):
                vector_size = len(self.embeddings.embed_query("dimension probe"))
                self.client.create_collection(
                    collection_name=collection,
                    vectors_config=qmodels.VectorParams(
                        size=vector_size, distance=qmodels.Distance.COSINE
                    ),
                )
                logger.info(
                    f"Created Qdrant collection '{collection}' (dim={vector_size})"
                )

            store = LCQdrantVectorStore(
                client=self.client,
                collection_name=collection,
                embedding=self.embeddings,
            )
            store.add_texts(chunks)
            logger.info(f"Upserted {len(chunks)} chunks into collection '{collection}'")
        except Exception as e:
            logger.error(f"Error upserting into collection '{collection}': {e}")
