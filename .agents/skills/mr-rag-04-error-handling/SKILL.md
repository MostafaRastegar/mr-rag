---
name: mr-rag-04-error-handling
description: Exception hierarchy and cross-layer error translation
---

# mr-rag-04-error-handling

## Usage

Use this skill when adding a new exception type, handling errors in a Pipeline or Adapter, or adding error handling to new API endpoints.

## Steps

1. Identify the layer where the error originates
2. Use the most specific exception type for the failure mode
3. Wrap external errors in domain exceptions at the Infrastructure layer
4. Wrap infrastructure errors in pipeline exceptions at the Pipeline layer
5. Translate domain exceptions to HTTP responses at the API layer

## Exception Hierarchy

```
RAGException (base)
├── DocumentLoadError    — File not found, parse failure
├── EmbeddingError       — OpenRouter embedding API failure
├── VectorStoreError     — ChromaDB operation failure
├── LLMError             — OpenRouter LLM API failure
├── IngestionError       — Ingestion pipeline failure
└── RetrievalError       — Retrieval/generation pipeline failure
```

## Error Translation Chain

```
External API Error (httpx)
  → Infrastructure Adapter: catch → wrap in domain exception (EmbeddingError)
    → Pipeline: catch → wrap in pipeline exception (RetrievalError)
      → API Route: catch → translate to HTTPException
```

### Infrastructure Layer Pattern

```python
try:
    response = self._client.post(...)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    raise EmbeddingError(f"OpenRouter embedding failed: {e}") from e
```

### Pipeline Layer Pattern

```python
try:
    query_embedding = self._embedding.embed_query(question)
except Exception as e:
    raise RetrievalError(f"Failed to embed query: {e}") from e
```

### API Layer Pattern

```python
try:
    answer = rag.answer(request.question)
except RetrievalError as e:
    raise HTTPException(status_code=500, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
```

## Should / Should Not

✅ Do: Always chain exceptions with `from e` to preserve context
✅ Do: Log with `logger.exception()` at the catch site for stack traces
✅ Do: Handle `FileNotFoundError` separately in route handlers (404 vs 500)
❌ Don't: Let raw httpx/chromadb exceptions bubble up to the API layer
❌ Don't: Swallow exceptions silently — always log or re-raise