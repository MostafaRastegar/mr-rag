"""
OpenRouter Embedding Adapter.

Implements the EmbeddingPort interface using httpx to call
the OpenRouter embeddings API directly, without LangChain dependency.
Supports optional caching via CachePort for repeated queries.
"""

import json
import logging
from typing import List, Optional

import httpx

from app.config import settings
from app.core.exceptions import EmbeddingError
from app.core.ports import CachePort, EmbeddingPort

logger = logging.getLogger(__name__)


class OpenRouterEmbedding(EmbeddingPort):
    """
    Generates text embeddings via the OpenRouter API.

    Uses httpx directly to avoid incompatibility issues between
    the openai library and OpenRouter's API.

    If a CachePort instance is provided, query embeddings are cached
    so that repeated questions return immediately without an API call.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        cache: CachePort | None = None,
    ) -> None:
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self._cache = cache

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string.

        If a cache is configured, checks the cache first.
        On cache hit, returns immediately. On cache miss, calls the API,
        stores the result, and returns it.
        """
        # Try cache first
        if self._cache is not None:
            prompt = text
            llm_string = json.dumps({"model": self.model}, sort_keys=True)
            cached = self._cache.lookup(prompt, llm_string)
            if cached is not None:
                logger.info("Embedding cache HIT for query")
                return json.loads(cached)

        # No cache hit, call the API
        results = self.embed_documents([text])
        embedding = results[0]

        # Store in cache
        if self._cache is not None:
            prompt = text
            llm_string = json.dumps({"model": self.model}, sort_keys=True)
            self._cache.update(prompt, llm_string, json.dumps(embedding))
            logger.info("Embedding cache UPDATED for query")

        return embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of text strings."""
        if not texts:
            return []

        try:
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
        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenRouter embedding API error: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise EmbeddingError(
                f"Embedding API returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("OpenRouter embedding request failed: %s", str(e))
            raise EmbeddingError(f"Embedding request failed: {e}") from e
