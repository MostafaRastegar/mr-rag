"""
Vector store repository using LangChain's Chroma integration.

This module provides a clean repository layer for CRUD operations
on vector embeddings using langchain-chroma. It follows the Single
Responsibility Principle by only handling database operations.
"""

from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.config import settings


class VectorStore:
    """Repository for storing and retrieving vector embeddings."""

    def __init__(
        self,
        collection_name: str = "rag_docs",
        embedding_function: Optional[Embeddings] = None,
    ) -> None:
        kwargs = {
            "collection_name": collection_name,
            "collection_metadata": {"hnsw:space": "cosine"},
        }
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function

        self._vector_store = Chroma(
            host=settings.chroma_host,
            port=settings.chroma_port,
            **kwargs,
        )

    @property
    def vector_store(self) -> Chroma:
        """Return the underlying LangChain Chroma instance."""
        return self._vector_store

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        """
        Add documents to the vector store.

        When an embedding_function is configured, embeddings are generated
        automatically from documents. Otherwise, embeddings must be provided.

        Args:
            ids: Unique identifiers for each document.
            documents: Original text content of each document.
            embeddings: Optional embedding vectors. Required if no
                embedding_function was provided at init.
            metadatas: Optional metadata for each document.
        """
        if metadatas is None:
            metadatas = [{} for _ in range(len(ids))]

        docs = [
            Document(page_content=doc, metadata=meta)
            for doc, meta in zip(documents, metadatas)
        ]

        if embeddings is not None:
            self._vector_store.add(
                ids=ids,
                documents=docs,
                embeddings=embeddings,
            )
        else:
            self._vector_store.add_documents(documents=docs, ids=ids)

    def search(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        top_k: int = 5,
    ) -> List[dict]:
        """
        Search for the most similar documents.

        Either query_embedding or query_text must be provided.
        When query_text is given and an embedding_function is configured,
        the embedding is generated automatically.

        Args:
            query_embedding: The embedding vector to search with.
            query_text: A text query to search with.
            top_k: Number of top results to return.

        Returns:
            A list of dicts with 'id', 'document', 'metadata', and 'distance'.
        """
        if query_text is not None:
            results = self._vector_store.similarity_search_with_relevance_scores(
                query_text, k=top_k
            )
        elif query_embedding is not None:
            # Use raw similarity search when only an embedding is available
            results = self._vector_store.similarity_search_by_vector(
                query_embedding, k=top_k
            )
            # similarity_search_by_vector returns list[Document], wrap with scores
            # Re-fetch with scores using a score-based method
            return self._search_by_vector_with_scores(query_embedding, top_k)
        else:
            raise ValueError("Either query_embedding or query_text must be provided")

        items = []
        for doc, score in results:
            items.append(
                {
                    "id": doc.metadata.get("id", ""),
                    "document": doc.page_content,
                    "metadata": {k: v for k, v in doc.metadata.items() if k != "id"},
                    "distance": round(1.0 - score, 4),
                }
            )
        return items

    def _search_by_vector_with_scores(
        self,
        query_embedding: List[float],
        top_k: int,
    ) -> List[dict]:
        """Search by embedding vector and return results with scores."""
        # Chroma's underlying collection query with embeddings
        collection = self._vector_store._collection
        if collection is None:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        items = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            items.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": metadata,
                    "distance": round(1.0 - distance, 4),
                }
            )
        return items

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self._vector_store._collection.count()

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        self._vector_store.delete_collection()
