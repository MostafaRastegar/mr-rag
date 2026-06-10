"""
Custom LangChain ChatModel for OpenRouter API.

Uses httpx for HTTP requests since the openai library (used internally
by langchain_openai) sends incompatible parameters to OpenRouter.
Implements LangChain's BaseChatModel interface for full compatibility.
"""

from typing import Any, Dict, List, Optional

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import settings


class OpenRouterChatModel(BaseChatModel):
    """LangChain-compatible ChatModel that calls OpenRouter via httpx."""

    model: str = settings.llm_model
    api_key: str = settings.openrouter_api_key
    base_url: str = settings.openrouter_base_url
    temperature: float = 0.7
    max_tokens: int = 1024

    @property
    def _llm_type(self) -> str:
        return "openrouter-chat"

    def _convert_messages(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, str]]:
        """Convert LangChain messages to OpenRouter API format."""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ChatMessage):
                converted.append({"role": msg.role, "content": msg.content})
            else:
                converted.append({"role": "user", "content": msg.content})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Call OpenRouter API and return a ChatResult."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if stop:
            payload["stop"] = stop

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

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        message = AIMessage(content=content)
        return ChatResult(
            generations=[ChatGeneration(message=message)],
            llm_output={
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "model_name": self.model,
            },
        )