"""
OpenRouter LLM Adapter.

Implements the LLMPort interface using httpx to call
the OpenRouter chat completions API directly, without LangChain dependency.
"""

import logging
from typing import List

import httpx

from app.config import settings
from app.core.domain import Message
from app.core.exceptions import LLMError
from app.core.ports import LLMPort

logger = logging.getLogger(__name__)


class OpenRouterLLM(LLMPort):
    """
    Generates chat completions via the OpenRouter API.

    Uses httpx directly to avoid incompatibility issues between
    the openai library and OpenRouter's API.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a response from the language model.
        """
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = httpx.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenRouter LLM API error: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise LLMError(
                f"LLM API returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("OpenRouter LLM request failed: %s", str(e))
            raise LLMError(f"LLM request failed: {e}") from e
