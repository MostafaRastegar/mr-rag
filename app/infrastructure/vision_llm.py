"""
Vision LLM Adapter for describing images using OpenRouter's VLM models.

Sends an image (base64-encoded) to nvidia/nemotron-3.5-super-vl:free
and returns a Persian text description.
"""

from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from app.config import settings
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class VisionLLM:
    """
    Describes images using a vision-language model via OpenRouter.

    Model: nvidia/nemotron-3.5-super-vl:free (free tier, image understanding)
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
        language: str = "fa",
    ) -> None:
        self.model = model or settings.vision_model
        self.base_url = base_url or settings.vision_base_url
        self.api_key = api_key or settings.openrouter_api_key
        self.timeout_s = timeout_s or settings.vision_timeout_s
        self.language = language

    def describe_image(
        self,
        image_base64: str,
        mime_type: str = "image/png",
        prompt: str | None = None,
    ) -> str:
        """
        Generate a text description of an image.

        Args:
            image_base64: Base64-encoded image data (without data URI prefix).
            mime_type: MIME type of the image (e.g. image/png, image/jpeg).
            prompt: Custom prompt. Defaults to a Persian description prompt.

        Returns:
            Text description of the image in Persian.
        """
        if prompt is None:
            prompt = (
                "این تصویر را به فارسی توضیح بده. تمام جزئیات مرئی، متن‌ها، "
                "شکل‌ها، نمودارها، روابط بین اجزاء و هر اطلاعاتی که برای پاسخ "
                "به سوالات آموزشی مفید باشد را ذکر کن. به صورت خلاصه و دقیق بنویس."
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "mr-rag-vision",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    logger.warning("Vision LLM returned no choices")
                    raise LLMError("Vision LLM returned no choices")
                content = choices[0].get("message", {}).get("content") or ""
                if not content.strip():
                    logger.warning(
                        "Vision LLM returned empty content; response keys: %s",
                        list(data.keys()),
                    )
                    raise LLMError("Vision LLM returned empty content")
                return content.strip()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Vision LLM error: %s - %s",
                e.response.status_code,
                e.response.text[:500],
            )
            if e.response.status_code in (422, 400, 415):
                # Provider-level media rejection — skip this image silently.
                raise LLMError(
                    f"Vision LLM rejected media ({e.response.status_code})"
                ) from e
            raise LLMError(
                f"Vision LLM returned {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error("Vision LLM request failed: %s", str(e))
            raise LLMError(f"Vision LLM request failed: {e}") from e

    def ping(self) -> bool:
        """
        Quick health check against OpenRouter with a short timeout guard.

        Sends a minimal completion request and returns True only if OpenRouter
        responds successfully within a capped timeout. Used to fail fast when
        the OpenRouter gateway is unreachable instead of blocking on a long
        vision request.
        """
        guard_timeout = min(self.timeout_s, 10.0)
        try:
            with httpx.Client(timeout=guard_timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "mr-rag-vision-ping",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning("Vision LLM ping failed: %s", str(e))
            return False


# Module-level convenience instance
vision_llm = VisionLLM()


def describe_image(image_base64: str, mime_type: str = "image/png") -> str:
    """Module-level shortcut: ``vision_llm.describe_image(image_base64)``."""
    return vision_llm.describe_image(image_base64, mime_type)
