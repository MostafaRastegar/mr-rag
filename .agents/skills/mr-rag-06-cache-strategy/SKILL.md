---
name: mr-rag-06-cache-strategy
description: Three-tier cache architecture with semantic matching
---

# mr-rag-06-cache-strategy

## Usage

Use this skill when working with caching logic, adding a new cache adapter, modifying TTL settings, or understanding the cache flow in the RAG pipeline.

## Steps

1. Identify which cache tier is needed: Embedding, LLM, or RAG Q&A
2. For a new cache adapter: implement `CachePort` from `app/core/ports.py`
3. Wire the cache in `app/main.py` with appropriate TTL
4. Use `if self._cache is not None` before any cache operation
5. Store values as JSON strings for schema evolution

## Cache Tiers

| Layer | TTL | Cache Key | What It Caches |
|-------|-----|-----------|----------------|
| Embedding | 1 hour | Query text hash | Query → embedding vector |
| LLM | 24 hours | Serialized messages | Messages → LLM response |
| RAG Q&A | 24 hours | Question text + semantic similarity | Question → full answer |

## RAG Cache: Two Sub-Layers

```
Question
→ [Exact Cache Check] → HIT → return cached Answer (<50ms)
→ MISS:
  → Embedding API
  → [Semantic Cache Check] (cosine ≥ 0.92) → HIT → return cached Answer (~1s)
  → MISS:
    → ChromaDB → LLM → Store in both caches → return Answer
```

## Cache Adapters

| Adapter | Backend | Persistence |
|---------|---------|-------------|
| `InMemoryCacheAdapter` | LangChain InMemoryCache | Ephemeral (lost on restart) |
| `SQLiteCacheAdapter` | LangChain SQLiteCache (SQLite file) | Persistent across restarts |
| `SemanticCacheAdapter` | In-memory hybrid (exact + semantic) | Ephemeral |

## LangChain Integration

- `InMemoryCacheAdapter` wraps `langchain_core.caches.InMemoryCache`
- `SQLiteCacheAdapter` wraps `langchain_community.cache.SQLiteCache` — eliminates custom sqlite3 code
- `SemanticCacheAdapter` uses LangChain's `InMemoryCache` for the exact-match sub-layer

## Cache Usage Pattern (in RAGPipeline)

```python
# Exact-match cache
cached = self._cache.lookup(question, llm_string)
if cached is not None:
    return Answer(text=json.loads(cached)["text"], sources=[])

# Semantic cache
cached = self._cache.lookup_semantic(query_embedding, threshold)
if cached is not None:
    return Answer(text=json.loads(cached)["text"], sources=[])

# Update both caches on miss
self._cache.update(question, llm_string, json.dumps({"text": answer_text}))
self._cache.update_semantic(query_embedding, json.dumps({"text": answer_text}))
```

## Should / Should Not

✅ Do: Use `CachePort` interface type for all cache parameters
✅ Do: Serialize cache values as JSON strings
✅ Do: Check `if self._cache is not None` before using cache
✅ Do: Store in BOTH exact and semantic caches on cache miss
❌ Don't: Store non-serializable objects directly in cache
❌ Don't: Add business logic inside cache adapters