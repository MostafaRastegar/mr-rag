"""
LLM service using custom OpenRouter ChatModel.

Uses OpenRouterChatModel (LangChain-compatible, httpx-based) to provide
a clean interface for chat completions via OpenRouter API.
"""

from typing import List, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.openrouter_llm import OpenRouterChatModel


class LLMService:
    """Handles chat completions using OpenRouter API via LangChain."""

    def __init__(self) -> None:
        self._client = OpenRouterChatModel()

    @property
    def client(self) -> BaseChatModel:
        """Return the underlying LangChain ChatModel instance."""
        return self._client

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
            temperature: Controls randomness.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.
        """
        # Convert dict messages to LangChain message objects
        langchain_messages = []
        for msg in messages:
            if msg["role"] == "system":
                langchain_messages.append(SystemMessage(content=msg["content"]))
            else:
                langchain_messages.append(HumanMessage(content=msg["content"]))

        # Apply temperature and max_tokens if they differ from defaults
        if temperature != 0.7 or max_tokens != 1024:
            client = OpenRouterChatModel(
                temperature=temperature,
                max_tokens=max_tokens,
            )
        else:
            client = self._client

        response = client.invoke(langchain_messages)
        return str(response.content)
