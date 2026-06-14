"""
Centralized configuration for the RAG application.

Uses pydantic-settings to load environment variables from .env file.
All configuration values are read from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Models
    embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    llm_model: str = "poolside/laguna-m.1:free"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8080

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 100

    # Retrieval
    top_k: int = 3
    retrieval_min_score: float = (
        0.15  # minimum cosine score to include a chunk in context
    )

    # Cache
    cache_type: str = "memory"  # "memory" or "sqlite"
    cache_db_path: str = "data/cache.db"
    cache_ttl_embedding: int = 3600  # 1 hour
    cache_ttl_llm: int = 86400  # 24 hours
    cache_maxsize: int = 10_000  # max in-memory items

    # Semantic cache (for RAG Q&A — matches similar questions via embedding similarity)
    cache_semantic_enabled: bool = True
    cache_semantic_threshold: float = 0.92  # cosine similarity threshold (0.0-1.0)
    cache_semantic_maxsize: int = 500  # max cached question-answer pairs in memory

    # Query Expansion (Stage 2)
    # When enabled, if the initial search finds no relevant chunks, the LLM
    # generates alternative phrasings of the user's question to improve retrieval.
    query_expansion_enabled: bool = False
    query_expansion_count: int = 3

    # Loose Prompt (Stage 3)
    # When enabled, if even query expansion finds no relevant chunks, the LLM
    # is prompted with a relaxed instruction that allows it to use its own
    # knowledge when the context is insufficient.
    loose_prompt_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
