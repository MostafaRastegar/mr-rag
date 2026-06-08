"""
Centralized configuration for the RAG application.

Uses pydantic-settings to load environment variables from .env file.
All configuration values are read from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenRouter
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Models
    embedding_model: str = "openai/text-embedding-ada-002"
    llm_model: str = "meta-llama/llama-3.3-70b-instruct"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8080

    # Chunking
    chunk_size: int = 1024
    chunk_overlap: int = 200

    # Retrieval
    top_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()