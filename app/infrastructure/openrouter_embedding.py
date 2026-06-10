"""
OpenRouter Embedding Adapter.

Implements the EmbeddingPort interface using httpx to call
the OpenRouter embeddings API directly, without LangChain dependency.
"""

import logging
from typing import List

import httpx

from app.config import settings
from app.core.exceptions import EmbeddingError
from app.core.ports import EmbeddingPort

logger = logging.getLogger(__name__)


class OpenRouterEmbedding(EmbeddingPort):
    """
    Generates text embeddings via the OpenRouter API.

    Uses httpx directly to avoid incompatibility issues between
    the openai library and OpenRouter's API.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string."""
        results = self.embed_documents([text])
        return results[0]

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
