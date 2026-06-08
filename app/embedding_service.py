"""
Embedding service abstraction for OpenRouter API.

This module provides a clean interface for generating text embeddings
using OpenRouter's API. It follows the Single Responsibility Principle
by only handling embedding operations.
"""

from typing import List

import httpx

from app.config import settings


class EmbeddingService:
    """Generates text embeddings using OpenRouter API."""

    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.model = settings.embedding_model

    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            httpx.HTTPError: If the API request fails.
        """
        response = httpx.post(
            url=f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": text,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for a list of texts.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of embedding vectors (each a list of floats).

        Raises:
            httpx.HTTPError: If the API request fails.
        """
        response = httpx.post(
            url=f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": texts,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]