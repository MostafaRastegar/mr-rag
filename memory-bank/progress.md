# Progress

## What Works
- **Core domain models** (`app/core/domain.py`) — All data classes defined
- **Port interfaces** (`app/core/ports.py`) — All 6 abstract interfaces
- **Exception hierarchy** (`app/core/exceptions.py`) — Custom exceptions for each layer
- **OpenRouter Embedding Adapter** — Direct HTTP via httpx, with optional CachePort
- **OpenRouter LLM Adapter** — Direct HTTP via httpx, with optional CachePort and **streaming SSE**
- **ChromaDB Vector Store Adapter** — Full CRUD with cosine similarity
- **JSON Document Loader** — Loads JSON files, supports `content`/`text` fields
- **LangChain Text Splitter** — RecursiveCharacterTextSplitter

### Cache Adapters (`app/infrastructure/cache.py`)
- `InMemoryCacheAdapter` — wraps LangChain's `InMemoryCache`
- `SQLiteCacheAdapter` — persistent SQLite-backed cache with TTL
- `SemanticCacheAdapter` — **hybrid**: exact-match (LangChain InMemoryCache) + semantic-match (cosine similarity)

### Ingestion Pipeline
- Orchestrates load → split → embed → store

### RAG Pipeline
- Two-layer cache: exact → semantic → full pipeline
- **`answer_stream()`** for streaming responses
- Score filtering (min_score=0.25) for token reduction
- **Three-stage cascading retrieval** for synonym-aware question answering

### FastAPI Routes
- `GET /health` — Service health check
- `POST /ingest` — Ingest JSON file
- `POST /chat` — Full answer
- `POST /chat/stream` — **Streaming SSE response**

### Configuration
- pydantic-settings with cache settings including semantic threshold
- Token optimization: chunk_size=512, top_k=3, min_score=0.25

### Scheduler Cron Job (`app/scheduler/`)
- JWT authentication with auto-refresh
- Paginated data fetching from Scraper API
- Job logic: fetch → save temp → ingest → cleanup
- Exponential backoff retry (60s, 120s, 240s, ... up to 5 attempts)
- Last-fetch log (`data/scheduler_log.json`)
- Configurable interval via `schedule` library

## What's Left to Build / Fix

### High Priority
- [ ] **Dockerfile** — needs `requirements.txt` sync with `pyproject.toml`
- [ ] **End-to-end integration test** — No test suite exists
- [ ] **Chunk ID collision risk** — Should use UUIDs or hash-based IDs

### Medium Priority
- [ ] **Error handling in ChromaVectorStore** — `add()` doesn't check for None collection
- [ ] **Scheduler admin endpoint** — `POST /scheduler/run` for manual trigger
- [ ] **Scheduler status endpoint** — `GET /scheduler/status` for last fetch log

### Low Priority
- [ ] **Rate limiting** — No rate limiting on API endpoints
- [ ] **Authentication** — No API key protection on endpoints
- [ ] **Metrics/monitoring** — No request metrics or tracing
- [ ] **Admin cache-clear endpoint** — No way to invalidate cache from API
- [ ] **Docker compose for scheduler** — Could be added as a separate service

## Known Issues
1. **Duplicate chunk IDs on re-ingestion** — IDs are simple incrementing counters
2. **No connection retry for ChromaDB** — Fails immediately if ChromaDB not ready
3. **OpenRouter free models may be rate-limited**
4. **Semantic cache is O(n)** — Linear scan of all entries. Fine for 500 entries, but may need optimization for larger caches
5. **Streaming response is synchronous for cache hits** — Full answer is buffered and yielded as one chunk

## Evolution of Decisions
| Date | Decision | Rationale |
|------|----------|-----------|
| Initial | Hexagonal architecture with Ports & Adapters | Maximum flexibility |
| 2026-06-10 | Three-tier cache architecture (embedding + LLM + RAG) | Different TTL/usage patterns |
| 2026-06-10 | InMemoryCacheAdapter wrapping LangChain InMemoryCache | Battle-tested cache with hash-key indirection |
| 2026-06-10 | SQLiteCacheAdapter as persistent alternative | Survives restarts |
| 2026-06-10 | **SemanticCacheAdapter** — hybrid exact + semantic | Covers both identical and semantically similar questions |
| 2026-06-10 | Default semantic threshold 0.92 | Balances precision and recall; configurable |
| 2026-06-10 | **Streaming support** via `POST /chat/stream` | Users see tokens progressively |
| 2026-06-10 | SSE streaming via `httpx.AsyncClient.stream()` | OpenRouter API supports SSE natively |
| 2026-06-10 | Token reduction: chunk_size=512, top_k=3, min_score=0.25 | ~70% savings in LLM tokens |
| 2026-06-10 | Scheduler cron job with `schedule` library | Lightweight, no system cron needed |
| 2026-06-14 | Three-stage cascading retrieval (Query Expansion + Loose Prompt) | Handle synonym-based questions and out-of-context queries |
