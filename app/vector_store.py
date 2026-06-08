"""
Vector store repository for ChromaDB.

This module provides a clean repository layer for CRUD operations
on vector embeddings using ChromaDB. It follows the Single Responsibility
Principle by only handling database operations.
"""

from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings


class VectorStore:
    """Repository for storing and retrieving vector embeddings."""

    def __init__(self, collection_name: str = "rag_docs") -> None:
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        """
        Add documents with their embeddings to the store.

        Args:
            ids: Unique identifiers for each document.
            embeddings: Embedding vectors for each document.
            documents: Original text content of each document.
            metadatas: Optional metadata for each document.
        """
        if metadatas is None:
            metadatas = [{} for _ in range(len(ids))]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[dict]:
        """
        Search for the most similar documents to a query embedding.

        Args:
            query_embedding: The embedding vector to search with.
            top_k: Number of top results to return.

        Returns:
            A list of dicts with 'id', 'document', 'metadata', and 'distance'.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        items = []
        for i in range(len(results["ids"][0])):
            items.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                }
            )
        return items

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self.collection.count()

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        self.client.delete_collection(self.collection.name)