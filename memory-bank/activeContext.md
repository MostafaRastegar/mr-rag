# Active Context

## Current Focus
The project's core implementation is complete with a **two-layer hybrid caching system** for performance improvement. A JSON parsing bug in the semantic cache hit path was identified and fixed.

## Recent Changes
- **Fixed semantic cache hit JSON parsing bug** in `app/pipeline/rag.py` — line 108 was returning `cached` (raw JSON string) directly as `Answer(text=cached)`. Fixed by adding `json.loads(cached)["text"]` with proper error handling, matching the exact-match cache path.

## Active Decisions & Considerations

### Two-Layer Cache Strategy
```
Question → Exact Match (hash) → HIT → return
                        ↓ MISS
           Embedding API (1 call)
                        ↓
           Semantic Match (cosine sim) → HIT → return (no search/LLM)
                        ↓ MISS
           ChromaDB Search + LLM Generation
                        ↓
           Store in both caches
```

### Semantic Cache Threshold
- Default `0.92` — requires 92% cosine similarity to consider a hit
- "میخواهم فسنجون درست کنم" vs "میخواهم فسنجون بپزم" → cosine similarity > 0.99 → ✅ Cache Hit

## Important Context Notes
- Semantic cache only works for the RAG pipeline (question → answer), not for individual LLM/embedding calls
- The embedding API call happens before semantic cache lookup — no extra overhead
- Exact-match semantic similarity comparison is O(n) where n = number of cached entries (default max 500)