---
name: mr-rag-10-rag-pipeline
description: Retrieval-Augmented Generation pipeline with caching, streaming, and token reduction
---

# mr-rag-10-rag-pipeline

## Usage

Use this skill when modifying the RAG pipeline, adding new retrieval/generation steps, tuning token reduction parameters, or understanding the cache flow.

## Steps

1. Check exact-match cache first (fastest, no embedding needed)
2. Embed the question
3. Check semantic cache (embedding similarity)
4. Search vector store with query embedding
5. Filter low-relevance chunks using `retrieval_min_score` (default: 0.25)
6. Build context from filtered chunks
7. Call LLM with system prompt and context
8. Store result in both exact and semantic caches

## Pipeline Flow

```
Question
→ [Exact Cache Check] → HIT → return cached Answer
→ MISS:
  → Embedding API
  → [Semantic Cache Check] (cosine ≥ 0.92) → HIT → return cached Answer
  → MISS:
    → ChromaDB search (top_k=3)
    → Filter low-relevance (min_score=0.25)
    → Build context from filtered chunks
    → LLM API
    → Store in both caches
    → return Answer
```

## Token Reduction

```python
min_score = settings.retrieval_min_score  # default: 0.25
if min_score > 0:
    filtered = [r for r in results if r.score >= min_score]
    results = filtered if filtered else results[:1]
```

## Context Building

```python
def _build_context(self, results: List[SearchResult]) -> str:
    context_parts = []
    for i, result in enumerate(results, 1):
        context_parts.append(f"[Document {i}] {result.chunk.text}")
    return "\n\n".join(context_parts)
```

## System Prompt

```python
SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Use only the information from the context to answer. "
    "If the context doesn't contain enough information, say so clearly."
)
```

## No Results Handling

```python
if not results:
    answer = Answer(text="I couldn't find any relevant information to answer your question.", sources=[])
    if self._cache is not None:
        self._cache.update(question, llm_string, json.dumps({"text": answer.text}))
    return answer
```

## Should / Should Not

✅ Do: Check exact-match cache first (fastest — no embedding API call)
✅ Do: Cache "no results" answers to avoid repeated empty searches
✅ Do: Validate cached JSON structure with try/except
❌ Don't: Include sources in cached answers — sources are not stored
❌ Don't: Forget to check `cache_semantic_enabled` before semantic lookup