"""
Custom LangChain Embeddings for OpenRouter API.

Uses httpx for HTTP requests since the openai library (used internally
by langchain_openai) sends incompatible parameters to OpenRouter.
Implements LangChain's Embeddings interface for full compatibility.
"""

from typing import List

import httpx
from langchain_core.embeddings import Embeddings

from app.config import settings


class OpenRouterEmbeddings(Embeddings):
    """LangChain-compatible Embeddings that calls OpenRouter via httpx."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call OpenRouter embeddings API."""
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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        if not texts:
            return []
        return self._call_api(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self._call_api([text])[0]