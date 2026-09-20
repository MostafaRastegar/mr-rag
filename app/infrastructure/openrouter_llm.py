"""
OpenRouter LLM Adapter.

Implements the LLMPort interface using httpx to call
the OpenRouter chat completions API directly, without LangChain dependency.
Supports optional caching via CachePort for repeated requests.
"""

import hashlib
import json
import logging
import time
from typing import Any, AsyncGenerator, List, Optional

import httpx

from app.config import settings
from app.core.domain import Message
from app.core.exceptions import LLMError
from app.core.ports import CachePort, LLMPort

logger = logging.getLogger(__name__)

# HTTP status codes that indicate a transient provider failure worth retrying
# (the Nvidia free tier intermittently returns 503 provider_overloaded).
_TRANSIENT_STATUS_CODES = {408, 429, 502, 503, 504}
# Base delay (seconds) for exponential backoff between transient retries.
_TRANSIENT_RETRY_BASE_DELAY = 2.0


class OpenRouterLLM(LLMPort):
    """
    Generates chat completions via the OpenRouter API.

    Uses httpx directly to avoid incompatibility issues between
    the openai library and OpenRouter's API.

    If a CachePort instance is provided, responses are cached
    using a hash of (serialized messages + model + temperature + max_tokens)
    as the cache key. On subsequent identical requests, the cached
    response is returned immediately without an API call.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = settings.response_max_token,
        cache: CachePort | None = None,
    ) -> None:
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._cache = cache

    def _effective_reasoning(self) -> dict:
        """
        Build the OpenRouter `reasoning` payload parameter.

        Free-tier reasoning models (e.g. nvidia/nemotron-3-ultra) default to
        "reasoning enabled". Those reasoning tokens count against `max_tokens`,
        which left little budget for the visible answer and produced short,
        truncated replies — one of the reported quality problems.

        Disable reasoning for RAG generation calls (verbatim extraction and
        formatting work does not benefit from extended thinking) but allow
        callers to opt back in via settings.
        """
        if settings.llm_reasoning_enabled:
            return {}
        return {"reasoning": {"enabled": False, "exclude": True}}

    def _serialize_messages(self, messages: List[Message]) -> str:
        """Serialize messages to a JSON string for cache key generation."""
        return json.dumps(
            [{"role": m.role, "content": m.content} for m in messages],
            sort_keys=True,
        )

    def _build_cache_key(
        self, messages: List[Message], temperature: float, max_tokens: int
    ) -> tuple[str, str]:
        """
        Build (prompt, llm_string) tuple for cache lookup.

        Returns:
            A tuple of (prompt, llm_string) where:
            - prompt is the serialized messages
            - llm_string is the serialized model configuration
        """
        prompt = self._serialize_messages(messages)
        llm_config = json.dumps(
            {
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
        )
        return prompt, llm_config

    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = settings.response_max_token,
    ) -> str:
        """
        Generate a response from the language model.

        If a cache is configured, checks the cache first before
        calling the API. On cache hit, returns immediately.
        On cache miss, calls the API, stores the result, and returns it.
        """
        # Try cache first
        if self._cache is not None:
            prompt, llm_string = self._build_cache_key(
                messages, temperature, max_tokens
            )
            cached = self._cache.lookup(prompt, llm_string)
            if cached is not None:
                logger.info("LLM cache HIT — returning cached response")
                return cached

        # No cache hit, call the API
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(self._effective_reasoning())

        try:
            # Transient OpenRouter failures (Nvidia free tier frequently returns
            # 503 provider_overloaded). Retry with short backoff instead of
            # surfacing a 500 to the user.
            response: httpx.Response | None = None
            last_error: Exception | None = None
            for attempt in range(settings.llm_retry_attempts):
                try:
                    response = httpx.post(
                        url=f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=settings.llm_timeout_seconds,
                    )
                    if response.status_code in _TRANSIENT_STATUS_CODES:
                        wait = _TRANSIENT_RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            "OpenRouter transient error %s (attempt %d/%d) — retrying in %.1fs",
                            response.status_code,
                            attempt + 1,
                            settings.llm_retry_attempts,
                            wait,
                        )
                        time.sleep(wait)
                        continue
                    break
                except httpx.RequestError as e:
                    last_error = e
                    wait = _TRANSIENT_RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "OpenRouter request error (attempt %d/%d): %s — retrying in %.1fs",
                        attempt + 1,
                        settings.llm_retry_attempts,
                        str(e),
                        wait,
                    )
                    time.sleep(wait)
            if response is None:
                raise LLMError(
                    f"LLM request failed after {settings.llm_retry_attempts} attempts: {last_error}"
                ) from last_error
            response.raise_for_status()
            data = response.json()
            # OpenRouter reports in-band provider failures inside HTTP 200
            # responses (no "choices" at all), e.g.
            # {"error": {"code": 503, "message": ...}} — check before extracting.
            if data.get("error"):
                raise LLMError(
                    f"LLM upstream provider error: {data['error'].get('message', data['error'])}"
                )
            result = data["choices"][0]["message"]["content"]
            # Reasoning models can return a reasoning-only message (empty
            # visible content) when the token budget is exhausted by thinking.
            if result is None or result == "":
                reasoning_excerpt = (data["choices"][0]["message"].get("reasoning") or "")[:200]
                logger.warning(
                    "LLM returned empty content (reasoning exhausted budget?): %s",
                    reasoning_excerpt,
                )
                raise LLMError(
                    "LLM returned an empty answer — the model spent the whole "
                    "token budget on reasoning. Try reducing context or disabling reasoning."
                )
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

        # Store in cache
        if self._cache is not None:
            prompt, llm_string = self._build_cache_key(
                messages, temperature, max_tokens
            )
            self._cache.update(prompt, llm_string, result)
            logger.info("LLM cache UPDATED")

        return result

    async def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = settings.response_max_token,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the language model.

        Uses OpenRouter's SSE (Server-Sent Events) stream mode to yield
        tokens one by one as they arrive. This allows the client to display
        the response progressively instead of waiting for the full response.

        Cache is checked first. On cache hit, yields the full cached response.
        On cache miss, streams from the API and caches the full response.

        Args:
            messages: Conversation messages.
            temperature: Controls randomness (0.0 to 1.0).
            max_tokens: Maximum tokens in the response.

        Yields:
            Tokens of the generated text as they arrive from the API.
        """
        # Try cache first
        if self._cache is not None:
            prompt, llm_string = self._build_cache_key(
                messages, temperature, max_tokens
            )
            cached = self._cache.lookup(prompt, llm_string)
            if cached is not None:
                logger.info("LLM streaming cache HIT — yielding cached response")
                yield cached
                return

        # No cache hit, stream from API
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        payload.update(self._effective_reasoning())

        full_response_parts: List[str] = []
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                full_response_parts.append(delta)
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError) as e:
                            logger.debug("Ignoring malformed SSE chunk: %s", e)
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenRouter LLM stream error: %s - %s",
                e.response.status_code,
                await e.response.aread(),
            )
            raise LLMError(
                f"LLM streaming returned {e.response.status_code}: {await e.response.aread()}"
            ) from e
        except httpx.RequestError as e:
            logger.error("OpenRouter LLM stream request failed: %s", str(e))
            raise LLMError(f"LLM streaming request failed: {e}") from e

        # Store full response in cache
        full_text = "".join(full_response_parts)
        if self._cache is not None and full_text:
            prompt, llm_string = self._build_cache_key(
                messages, temperature, max_tokens
            )
            self._cache.update(prompt, llm_string, full_text)
            logger.info("LLM streaming cache UPDATED (%d chars)", len(full_text))
