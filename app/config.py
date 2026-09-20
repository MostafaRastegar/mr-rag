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
    # NOTE: embedding_model must be a model served by OpenRouter's /embeddings
    # endpoint (live-verified). Chat-only models such as poolside/laguna-s-2.1:free
    # are rejected with HTTP 400 "Model does not exist".
    embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    llm_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"

    # Reasoning control for OpenRouter chat models. Reasoning-capable models
    # (e.g. nvidia/nemotron-3-ultra) default to "reasoning enabled"; those
    # thinking tokens count against `max_tokens`, which starved the visible
    # answer and produced short/truncated RAG replies. Disabled by default so
    # the full token budget goes to the answer.
    llm_reasoning_enabled: bool = False
    # Per-request HTTP timeout (seconds) for chat-completion calls. The free
    # Nvidia tier can take ~40s for a 1000-char answer, so the previous 120s
    # budget was kept, but it is now configurable.
    llm_timeout_seconds: int = 120
    # Retries for transient OpenRouter provider errors (503 overloaded etc.)
    # with exponential backoff, instead of failing the request immediately.
    llm_retry_attempts: int = 3

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8080

    # Chunking
    # Raised from 512 (the minimum acceptable value) because long Persian
    # sentences were being cut mid-thought, producing fragmented context.
    chunk_size: int = 800
    chunk_overlap: int = 120

    # Retrieval
    response_max_token: int = 2048
    top_k: int = 5
    # Number of candidates fetched BEFORE filtering/reranking. Truncated to
    # at least `top_k` so the candidate pool is always large enough.
    fetch_k: int = 20
    retrieval_min_score: float = (
        0.35  # minimum cosine score to include a chunk in context
    )

    # Relevance cascade calibration.
    # `retrieval_low_relevance_threshold` is the average-score floor below which
    # the pipeline considers Stage 1 retrieval weak and escalates to the
    # cascade stages. Previously hardcoded as 0.30 inside the pipeline.
    #
    # Calibrated against scripts/eval_retrieval.py on the current corpus, where
    # dense top-k scores ranged 0.19-0.69 (avg 0.45). Values below ~0.30
    # therefore never filtered anything.
    #
    # NOTE: the hybrid retriever normalizes fused scores onto 0.0-1.0, so these
    # two thresholds only discriminate on the dense path. With hybrid search
    # enabled, `rerank_min_score` is the effective quality gate.
    retrieval_low_relevance_threshold: float = 0.45

    # LLM-based reranking (no rerank model is available on OpenRouter).
    # When enabled, the candidate pool is scored by the LLM and only the best
    # `rerank_top_n` chunks are kept. Retrieved ordering is preserved for the
    # remaining slots so a rerank failure degrades gracefully.
    rerank_enabled: bool = True
    rerank_top_n: int = 5
    # Chunks below this rerank score (0-10 scale) are dropped.
    rerank_min_score: float = 3.0
    rerank_max_tokens: int = 1024

    # Hybrid search (BM25 keyword + dense vector) via LangChain
    # BM25Retriever + EnsembleRetriever. Weight `hybrid_bm25_weight` is the
    # share given to BM25; the remainder goes to the dense retriever.
    hybrid_search_enabled: bool = True
    hybrid_bm25_weight: float = 0.4

    # Multi-query retrieval (LangChain MultiQueryRetriever). Generates
    # alternative phrasings and merges results with Reciprocal Rank Fusion.
    multi_query_enabled: bool = False
    multi_query_count: int = 3

    # Cache
    cache_type: str = "memory"  # "memory" or "sqlite"
    cache_db_path: str = "data/cache.db"
    cache_ttl_embedding: int = 3600  # 1 hour
    cache_ttl_llm: int = 86400  # 24 hours
    cache_maxsize: int = 10_000  # max in-memory items

    # Semantic cache (for RAG Q&A — matches similar questions via embedding similarity)
    cache_semantic_enabled: bool = True
    # Cosine similarity threshold (0.0-1.0). Raised from 0.92 because the
    # nvidia embedding model produces high inter-question similarity, which
    # made unrelated questions collide and return wrong cached answers.
    cache_semantic_threshold: float = 0.97
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore",}


settings = Settings()
