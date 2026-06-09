"""
LLM service using LangChain's ChatOpenAI.
Uses OpenRouter API via custom base_url.
"""

from typing import List, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings


class LLMService:
    """Handles chat completions using OpenRouter API via LangChain."""

    def __init__(self) -> None:
        self._client = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=0.7,
            max_completion_tokens=1024,
        )

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
            client = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
        else:
            client = self._client

        response = client.invoke(langchain_messages)
        return response.content
