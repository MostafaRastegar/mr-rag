"""
Embedding service abstraction using custom OpenRouter Embeddings.

Uses OpenRouterEmbeddings (LangChain-compatible, httpx-based) to provide
a clean interface for generating text embeddings via OpenRouter API.
"""

from typing import List

from langchain_core.embeddings import Embeddings

from app.openrouter_embeddings import OpenRouterEmbeddings


class EmbeddingService:
    """Generates text embeddings using OpenRouter API."""

    def __init__(self) -> None:
        self._embeddings = OpenRouterEmbeddings()

    @property
    def embeddings(self) -> Embeddings:
        """Return the underlying LangChain Embeddings instance."""
        return self._embeddings

    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        return self._embeddings.embed_query(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for a list of texts.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of embedding vectors (each a list of floats).
        """
        return self._embeddings.embed_documents(texts)
