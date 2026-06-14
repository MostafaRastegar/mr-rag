---
name: mr-rag-08-streaming
description: Server-Sent Events (SSE) streaming for real-time LLM responses
---

# mr-rag-08-streaming

## Usage

Use this skill when implementing or modifying streaming endpoints, adding streaming support to a new LLM adapter, or understanding cache behavior with streaming.

## Steps

1. Ensure the route handler is `async def` and returns `StreamingResponse`
2. The pipeline method must return `AsyncGenerator[str, None]`
3. The LLM adapter must use `httpx.AsyncClient.stream()` for SSE
4. Handle cache hits by yielding the full cached answer and returning immediately
5. Collect all tokens in a list for caching after streaming completes

## Architecture

```
Client → FastAPI SSE → RAGPipeline.answer_stream() → OpenRouterLLM.generate_stream()
                                                        ↓
                                                  httpx.AsyncClient.stream()
                                                        ↓
                                                  yield token → yield token → ...
```

### Route Handler

```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return StreamingResponse(
        rag.answer_stream(request.question),
        media_type="text/plain",
    )
```

### LLM Stream Method

```python
async def generate_stream(self, messages, ...) -> AsyncGenerator[str, None]:
    async with self._async_client.stream(
        "POST", f"{self._base_url}/chat/completions",
        json={"messages": [...], "stream": True, ...},
        timeout=120.0,
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                token = json.loads(data)["choices"][0]["delta"].get("content", "")
                if token:
                    yield token
```

### Cache Behavior

- Cache hit: yield full answer as one chunk, then return
- Cache miss: stream progressively, cache after completion

```python
# Cache hit
if self._cache is not None:
    cached = self._cache.lookup(question, llm_string)
    if cached is not None:
        yield json.loads(cached)["text"]
        return
```

## Should / Should Not

✅ Do: Use `AsyncGenerator[str, None]` as the return type
✅ Do: Use `httpx.AsyncClient.stream()` with `async for line in response.aiter_lines()`
✅ Do: Collect tokens in a list for caching after streaming completes
❌ Don't: Use blocking HTTP calls in streaming endpoints
❌ Don't: Cache partial/empty responses
❌ Don't: Forget to make the route handler `async`