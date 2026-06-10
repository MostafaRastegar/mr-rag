# Progress

## What Works
- **Core domain models** (`app/core/domain.py`) — All data classes defined
- **Port interfaces** (`app/core/ports.py`) — All 6 abstract interfaces including `CachePort` with `lookup_semantic()`, `update_semantic()` و `LLMPort` با `generate_stream()`
- **Exception hierarchy** (`app/core/exceptions.py`) — Custom exceptions for each layer
- **OpenRouter Embedding Adapter** — Direct HTTP embedding via httpx, with optional CachePort
- **OpenRouter LLM Adapter** — Direct HTTP chat completions via httpx, with optional CachePort **و streaming SSE**
- **ChromaDB Vector Store Adapter** — Full CRUD with cosine similarity
- **JSON Document Loader** — Loads JSON files, supports `content`/`text` fields
- **LangChain Text Splitter** — RecursiveCharacterTextSplitter
- **Cache Adapters** (`app/infrastructure/cache.py`):
  - `InMemoryCacheAdapter` — wraps LangChain's `InMemoryCache`
  - `SQLiteCacheAdapter` — persistent SQLite-backed cache with TTL
  - `SemanticCacheAdapter` — **hybrid**: exact-match (LangChain InMemoryCache) + semantic-match (cosine similarity)
- **Ingestion Pipeline** — Orchestrates load → split → embed → store
- **RAG Pipeline** — Two-layer cache: exact → semantic → full pipeline, **با `answer_stream()` برای streaming پاسخ**
- **FastAPI Routes** — 4 endpoints: GET /health, POST /ingest, POST /chat, **POST /chat/stream**
- **Configuration** — pydantic-settings with cache settings including semantic threshold
- **Dependency Wiring** — Manual DI with cache instances

## What's Left to Build / Fix

### High Priority
- [ ] **Docker build fails** — Dockerfile references `requirements.txt`
- [ ] **End-to-end integration test** — No test suite exists
- [ ] **Chunk ID collision risk** — Should use UUIDs or hash-based IDs

### Medium Priority
- [ ] **Error handling in ChromaVectorStore** — `add()` doesn't check for None collection
- [ ] **Health check improvement** — More specific error handling
- [ ] **Ingestion file path** — Should validate within expected directories

### Low Priority
- [ ] **Rate limiting** — No rate limiting on API endpoints
- [ ] **Authentication** — No API key protection
- [ ] **Metrics/monitoring** — No request metrics or tracing
- [ ] **Admin cache-clear endpoint** — No way to invalidate cache from API

## Known Issues
1. **Duplicate chunk IDs on re-ingestion** — IDs are simple incrementing counters
2. **No connection retry for ChromaDB** — Fails immediately if ChromaDB not ready
3. **OpenRouter free models may be rate-limited**
4. **Semantic cache is O(n)** — Linear scan of all entries. Fine for 500 entries, but may need optimization for larger caches
5. **Streaming response is synchronous** — Not true streaming for cache hits; full answer is buffered and yielded as one chunk

## Evolution of Decisions
| Date | Decision | Rationale |
|------|----------|-----------|
| Initial | Hexagonal architecture with Ports & Adapters | Maximum flexibility |
| 2026-06-10 | Three-tier cache architecture (embedding + LLM + RAG) | Different TTL/usage patterns |
| 2026-06-10 | InMemoryCacheAdapter wrapping LangChain InMemoryCache | Battle-tested cache with hash-key indirection |
| 2026-06-10 | SQLiteCacheAdapter as persistent alternative | Survives restarts |
| 2026-06-10 | **SemanticCacheAdapter** — hybrid exact + semantic | Covers both identical and semantically similar questions |
| 2026-06-10 | Default semantic threshold 0.92 | Balances precision and recall; configurable |
| 2026-06-10 | **Streaming support** via `POST /chat/stream` | Users see tokens progressively, no need to wait for full response |
| 2026-06-10 | SSE streaming via `httpx.AsyncClient.stream()` | OpenRouter API supports SSE natively; async generator pattern |