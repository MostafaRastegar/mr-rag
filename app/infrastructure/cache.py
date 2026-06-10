"""
Cache adapters for the RAG system.

Provides caching implementations using LangChain's cache infrastructure
(BaseCache, InMemoryCache) plus a custom SQLite-based persistent cache.

These adapters wrap LangChain caches behind a clean CachePort interface,
which is injected into LLM, embedding, and pipeline components.
"""

import hashlib
import json
import logging
import math
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from langchain_core.caches import BaseCache as LangChainBaseCache
from langchain_core.caches import InMemoryCache as LangChainInMemoryCache
from langchain_core.outputs import Generation

from app.config import settings
from app.core.domain import Message
from app.core.ports import CachePort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter: InMemoryCacheAdapter
# ---------------------------------------------------------------------------


class InMemoryCacheAdapter(CachePort):
    """
    In-memory cache adapter wrapping LangChain's InMemoryCache.

    This cache is fast but ephemeral — data is lost on process restart.
    Suitable for short-lived caching during a single session.

    Uses hashed keys to keep memory usage predictable and avoid
    storing raw prompt/LLM strings in the lookup table.
    """

    def __init__(self, maxsize: int | None = 10_000) -> None:
        self._cache = LangChainInMemoryCache(maxsize=maxsize)
        self._maxsize = maxsize

    def _build_key(self, prompt: str, llm_string: str) -> str:
        """Build a deterministic hash key from prompt and llm_string."""
        raw = f"{prompt}||{llm_string}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def lookup(self, prompt: str, llm_string: str) -> Optional[str]:
        """Look up a cached response by prompt and LLM configuration.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.

        Returns:
            The cached text if found, otherwise None.
        """
        key = self._build_key(prompt, llm_string)
        result = self._cache.lookup(key, "default")
        if result is not None and len(result) > 0:
            logger.debug("Cache HIT for key=%s...", key[:12])
            return result[0].text
        logger.debug("Cache MISS for key=%s...", key[:12])
        return None

    def update(self, prompt: str, llm_string: str, value: str) -> None:
        """Store a response in the cache.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.
            value: The response text to cache.
        """
        key = self._build_key(prompt, llm_string)
        self._cache.update(key, "default", [Generation(text=value)])
        logger.debug("Cache UPDATED for key=%s...", key[:12])

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("In-memory cache cleared")


# ---------------------------------------------------------------------------
# Adapter: SQLiteCacheAdapter
# ---------------------------------------------------------------------------


class SQLiteCacheAdapter(CachePort):
    """
    Persistent cache adapter backed by SQLite.

    Data survives process restarts, making it suitable for production use.
    Uses a simple key-value table where keys are SHA-256 hashes of
    (prompt, llm_string) tuples.

    Thread-safe for concurrent access.
    """

    def __init__(
        self, db_path: str | None = None, ttl_seconds: int | None = None
    ) -> None:
        self._db_path = str(db_path or settings.cache_db_path)
        self._ttl_seconds = ttl_seconds or settings.cache_ttl_llm
        self._lock = threading.Lock()

        # Ensure the directory exists
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self) -> None:
        """Create the cache table if it doesn't exist."""
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=10)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        key_hash TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                    """)
                conn.commit()
            finally:
                conn.close()
        logger.info(
            "SQLite cache initialized at %s (TTL=%ds)", self._db_path, self._ttl_seconds
        )

    def _build_key(self, prompt: str, llm_string: str) -> str:
        """Build a deterministic hash key from prompt and llm_string."""
        raw = f"{prompt}||{llm_string}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _is_expired(self, created_at: float) -> bool:
        """Check if a cached entry has expired based on TTL."""
        return (time.time() - created_at) > self._ttl_seconds

    def lookup(self, prompt: str, llm_string: str) -> Optional[str]:
        """Look up a cached response by prompt and LLM configuration.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.

        Returns:
            The cached text if found and not expired, otherwise None.
        """
        key = self._build_key(prompt, llm_string)
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=10)
            try:
                cursor = conn.execute(
                    "SELECT value, created_at FROM cache WHERE key_hash = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if row is None:
                    logger.debug("SQLite cache MISS for key=%s...", key[:12])
                    return None

                value_json, created_at = row
                if self._is_expired(created_at):
                    logger.debug("SQLite cache EXPIRED for key=%s...", key[:12])
                    conn.execute("DELETE FROM cache WHERE key_hash = ?", (key,))
                    conn.commit()
                    return None

                data = json.loads(value_json)
                logger.debug("SQLite cache HIT for key=%s...", key[:12])
                return data["text"]
            finally:
                conn.close()

    def update(self, prompt: str, llm_string: str, value: str) -> None:
        """Store a response in the cache.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.
            value: The response text to cache.
        """
        key = self._build_key(prompt, llm_string)
        value_json = json.dumps({"text": value})

        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=10)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key_hash, value, created_at) VALUES (?, ?, ?)",
                    (key, value_json, time.time()),
                )
                conn.commit()
                logger.debug("SQLite cache UPDATED for key=%s...", key[:12])
            finally:
                conn.close()

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=10)
            try:
                conn.execute("DELETE FROM cache")
                conn.commit()
                logger.info("SQLite cache cleared")
            finally:
                conn.close()

    def clear_expired(self) -> int:
        """Remove all expired entries and return the count removed."""
        cutoff = time.time() - self._ttl_seconds
        with self._lock:
            conn = sqlite3.connect(self._db_path, timeout=10)
            try:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE created_at < ?", (cutoff,)
                )
                conn.commit()
                removed = cursor.rowcount
                if removed:
                    logger.info("Cleared %d expired cache entries", removed)
                return removed
            finally:
                conn.close()


# ---------------------------------------------------------------------------
# Utility: cosine similarity
# ---------------------------------------------------------------------------


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity in range [-1.0, 1.0].
    """
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for ai, bi in zip(a, b):
        dot += ai * bi
        norm_a += ai * ai
        norm_b += bi * bi
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    if denom == 0.0:
        return 0.0
    return dot / denom


# ---------------------------------------------------------------------------
# Adapter: SemanticCacheAdapter (Hybrid: exact-match + semantic-match)
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    """Internal entry for the semantic cache."""

    embedding: List[float]
    answer: str
    created_at: float
    access_count: int = 0

    def is_expired(self, ttl: float) -> bool:
        """Check if this entry has expired."""
        return (time.time() - self.created_at) > ttl


class SemanticCacheAdapter(CachePort):
    """
    Hybrid in-memory cache supporting both exact-match and semantic-match lookups.

    **Exact-match**: SHA-256 hash of (prompt, llm_string) → answer.
    Uses LangChain's InMemoryCache internally. Instant O(1) lookup.

    **Semantic-match**: Stores query embeddings alongside answers.
    When a new query comes in, its embedding is compared against all stored
    embeddings using cosine similarity. If the most similar entry exceeds
    the configured threshold, its answer is returned as a cache hit.

    This means:
    - Identical questions → exact match (instant, no embedding needed)
    - Similar questions → semantic match (e.g. "مواد اولیه پیتزا چیست؟"
      and "مواد اولیه پیتزا چیه؟" will both hit the same cache entry)

    Thread-safe for concurrent access.
    """

    def __init__(
        self,
        maxsize: int = 500,
        ttl_seconds: int = 86400,
        default_threshold: float = 0.92,
    ) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._default_threshold = default_threshold

        # Exact-match cache (LangChain InMemoryCache)
        self._exact_cache = LangChainInMemoryCache(maxsize=maxsize)

        # Semantic-match cache
        self._entries: List[_CacheEntry] = []
        self._lock = threading.Lock()

        logger.info(
            "SemanticCacheAdapter initialized (maxsize=%d, ttl=%ds, threshold=%.2f)",
            maxsize,
            ttl_seconds,
            default_threshold,
        )

    # ------------------------------------------------------------------
    # Exact-match (hash-based, LangChain InMemoryCache)
    # ------------------------------------------------------------------

    def _build_exact_key(self, prompt: str, llm_string: str) -> str:
        """Build a deterministic hash key from prompt and llm_string."""
        raw = f"{prompt}||{llm_string}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def lookup(self, prompt: str, llm_string: str) -> Optional[str]:
        """Exact-match lookup using SHA-256 hash key.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.

        Returns:
            The cached text if an exact textual match is found, otherwise None.
        """
        key = self._build_exact_key(prompt, llm_string)
        result = self._exact_cache.lookup(key, "default")
        if result is not None and len(result) > 0:
            logger.debug("SemanticCache (exact) HIT for key=%s...", key[:12])
            return result[0].text
        return None

    def update(self, prompt: str, llm_string: str, value: str) -> None:
        """Store a response in the exact-match cache.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.
            value: The response text to cache.
        """
        key = self._build_exact_key(prompt, llm_string)
        self._exact_cache.update(key, "default", [Generation(text=value)])
        logger.debug("SemanticCache (exact) UPDATED for key=%s...", key[:12])

    def clear(self) -> None:
        """Clear all cached entries (both exact and semantic)."""
        self._exact_cache.clear()
        with self._lock:
            self._entries.clear()
        logger.info("SemanticCache cleared")

    # ------------------------------------------------------------------
    # Semantic cache (embedding-based cosine similarity)
    # ------------------------------------------------------------------

    def lookup_semantic(
        self, embedding: List[float], threshold: Optional[float] = None
    ) -> Optional[str]:
        """
        Look up the most semantically similar cached answer.

        Compares the query embedding against all stored entries using
        cosine similarity. Returns the answer of the best match if its
        similarity exceeds the threshold.

        Args:
            embedding: The query embedding vector.
            threshold: Minimum cosine similarity to consider a hit (0.0-1.0).
                       Falls back to self._default_threshold if not provided.

        Returns:
            The cached answer text if a match is found, otherwise None.
        """
        threshold = threshold if threshold is not None else self._default_threshold
        best_similarity = -1.0
        best_answer: Optional[str] = None
        best_entry: Optional[_CacheEntry] = None

        with self._lock:
            # Purge expired entries opportunistically
            self._entries = [e for e in self._entries if not e.is_expired(self._ttl)]

            for entry in self._entries:
                sim = _cosine_similarity(embedding, entry.embedding)
                if sim > best_similarity:
                    best_similarity = sim
                    best_answer = entry.answer
                    best_entry = entry

        if best_similarity >= threshold and best_answer is not None:
            if best_entry is not None:
                best_entry.access_count += 1
            logger.info(
                "Semantic cache HIT (similarity=%.4f, threshold=%.2f)",
                best_similarity,
                threshold,
            )
            return best_answer

        logger.debug(
            "Semantic cache MISS (best_similarity=%.4f, threshold=%.2f)",
            best_similarity,
            threshold,
        )
        return None

    def update_semantic(self, embedding: List[float], value: str) -> None:
        """
        Store an answer in the semantic cache keyed by its query embedding.

        Args:
            embedding: The query embedding vector.
            value: The answer text to cache.
        """
        entry = _CacheEntry(
            embedding=embedding,
            answer=value,
            created_at=time.time(),
        )
        with self._lock:
            # Evict least accessed entry if at capacity
            if len(self._entries) >= self._maxsize:
                oldest = min(self._entries, key=lambda e: e.access_count)
                self._entries.remove(oldest)
                logger.debug("Evicted oldest semantic cache entry")

            self._entries.append(entry)
            logger.debug(
                "Semantic cache UPDATED (total entries: %d/%d)",
                len(self._entries),
                self._maxsize,
            )

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = len(self._entries)
            total_accesses = sum(e.access_count for e in self._entries)
        return {
            "type": "semantic_hybrid",
            "entries": total,
            "maxsize": self._maxsize,
            "total_accesses": total_accesses,
            "ttl_seconds": self._ttl,
            "threshold": self._default_threshold,
        }
