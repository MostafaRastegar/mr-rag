"""
ChromaDB Vector Store Adapter.

Implements the VectorStorePort interface using the langchain-chroma library.
Provides persistence and retrieval for document embeddings.
"""

import logging
from typing import List

from langchain_chroma import Chroma

from app.config import settings
from app.core.domain import Chunk, SearchResult
from app.core.exceptions import VectorStoreError
from app.core.ports import VectorStorePort

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStorePort):
    """
    Vector store backed by ChromaDB.

    Uses langchain-chroma for its robust ChromaDB client integration,
    but operates at the Chroma collection level to avoid LangChain's
    Document coupling.
    """

    def __init__(
        self,
        collection_name: str = "rag_docs",
    ) -> None:
        self._collection_name = collection_name

        self._vector_store = Chroma(
            collection_name=collection_name,
            collection_metadata={"hnsw:space": "cosine"},
            host=settings.chroma_host,
            port=settings.chroma_port,
        )

    @property
    def _collection(self):
        """Access the underlying Chroma collection for low-level operations."""
        return self._vector_store._collection

    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        """
        Add chunks with their embeddings to the store.

        Args:
            chunks: The text chunks to store.
            embeddings: Corresponding embedding vectors.

        Returns:
            Number of chunks successfully added.
        """
        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]

        try:
            collection = self._collection
            if collection is None:
                raise VectorStoreError("Chroma collection is not initialized")
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info(
                "Added %d chunks to collection '%s'", len(chunks), self._collection_name
            )
            return len(chunks)
        except VectorStoreError:
            raise
        except Exception as e:
            logger.error("Failed to add chunks to vector store: %s", str(e))
            raise VectorStoreError(f"Failed to add chunks: {e}") from e

    def search(self, query_embedding: List[float], top_k: int) -> List[SearchResult]:
        """
        Search for the most similar chunks given a query embedding.

        Args:
            query_embedding: The embedding vector to search with.
            top_k: Number of top results to return.

        Returns:
            A list of SearchResult objects, sorted by relevance (closest first).
        """
        try:
            collection = self._collection
            if collection is None:
                logger.warning("Chroma collection is None, returning empty results")
                return []

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            search_results: List[SearchResult] = []
            for i in range(len(results["ids"][0])):
                raw_metadata = (
                    results["metadatas"][0][i] if results["metadatas"] else {}
                )
                metadata = dict(raw_metadata) if raw_metadata else {}
                chunk = Chunk(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i],
                    metadata=metadata,
                )
                distance = results["distances"][0][i] if results["distances"] else 0.0
                score = 1.0 - distance
                search_results.append(SearchResult(chunk=chunk, score=round(score, 4)))

            return search_results
        except Exception as e:
            logger.error("Vector store search failed: %s", str(e))
            raise VectorStoreError(f"Search failed: {e}") from e

    def count(self) -> int:
        """Return the number of documents in the collection."""
        try:
            collection = self._collection
            if collection is None:
                return 0
            return collection.count()
        except Exception as e:
            logger.error("Failed to count documents: %s", str(e))
            raise VectorStoreError(f"Count failed: {e}") from e

    def delete(self, ids: list[str]) -> None:
        """
        Delete chunks from the store by their IDs.

        Args:
            ids: List of chunk IDs to delete.
        """
        if not ids:
            logger.warning("delete() called with empty ids list, skipping")
            return
        try:
            collection = self._collection
            if collection is None:
                raise VectorStoreError("Chroma collection is not initialized")
            collection.delete(ids=ids)
            logger.info("Deleted %d chunks from collection '%s'", len(ids), self._collection_name)
        except VectorStoreError:
            raise
        except Exception as e:
            logger.error("Failed to delete chunks: %s", str(e))
            raise VectorStoreError(f"Delete failed: {e}") from e

    def delete_by_metadata(self, key: str, value: str) -> int:
        """
        Delete chunks from the store by a metadata key-value pair.

        Args:
            key: The metadata field name.
            value: The metadata value to match.

        Returns:
            Number of deleted chunks.
        """
        try:
            collection = self._collection
            if collection is None:
                raise VectorStoreError("Chroma collection is not initialized")

            # First, find matching IDs
            results = collection.get(where={key: value})
            ids = results.get("ids", [])
            if not ids:
                logger.info(
                    "No chunks found with metadata %s=%s in collection '%s'",
                    key, value, self._collection_name,
                )
                return 0

            # Delete them
            collection.delete(ids=ids)
            logger.info(
                "Deleted %d chunks with metadata %s=%s from collection '%s'",
                len(ids), key, value, self._collection_name,
            )
            return len(ids)
        except VectorStoreError:
            raise
        except Exception as e:
            logger.error("Failed to delete chunks by metadata: %s", str(e))
            raise VectorStoreError(f"Delete by metadata failed: {e}") from e

    def get_all_ids(self) -> list[str]:
        """
        Return all chunk IDs in the store.

        Returns:
            A list of all chunk IDs.
        """
        try:
            collection = self._collection
            if collection is None:
                return []
            results = collection.get(ids=None)
            return results.get("ids", [])
        except Exception as e:
            logger.error("Failed to get all IDs: %s", str(e))
            raise VectorStoreError(f"Get all IDs failed: {e}") from e
