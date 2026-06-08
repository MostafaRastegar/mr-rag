"""
LLM service abstraction for OpenRouter API.

This module provides a clean interface for interacting with
language models via OpenRouter's API. It follows the Single
Responsibility Principle by only handling LLM chat completions.
"""

from typing import List, Dict

import httpx

from app.config import settings


class LLMService:
    """Handles chat completions using OpenRouter API."""

    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key
        self.base_url = settings.openrouter_base_url
        self.model = settings.llm_model

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: A list of message dicts with 'role' and 'content' keys.
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative).
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.

        Raises:
            httpx.HTTPError: If the API request fails.
        """
        response = httpx.post(
            url=f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]