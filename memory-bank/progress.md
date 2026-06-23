# Progress

## What Works
- **Core domain models** (`app/core/domain.py`) — All data classes defined
- **Port interfaces** (`app/core/ports.py`) — All 6 abstract interfaces
- **Exception hierarchy** (`app/core/exceptions.py`) — Custom exceptions for each layer
- **OpenRouter Embedding Adapter** — Direct HTTP via httpx, with optional CachePort
- **OpenRouter LLM Adapter** — Direct HTTP via httpx, with optional CachePort and **streaming SSE**
- **ChromaDB Vector Store Adapter** — Full CRUD with cosine similarity, null-collection safety checks
- **JSON Document Loader** — Uses LangChain JSONLoader with **auto-detection** of content field from priority key list (`content`, `text`, `body`, `description`, `article`, `markdown`, `html`, `summary`, `text_content`, `page_content`) + fallback to longest string value
- **JSON structure normalization** — Handles wrapped keys (`{"data": [...]}`, `{"results": [...]}`, etc.), list-of-strings, and single strings via `_normalize_json_structure()`
- **Temp-file strategy** — Normalised records written to temp file so JSONLoader always reads a consistent flat list of dicts
- **Markdown Document Loader** — Uses LangChain MarkdownHeaderTextSplitter (splits by headings)
- **Plain Text Document Loader** — Uses LangChain TextLoader
- **AutoDocumentLoader** — Dispatches by file extension (.json, .md, .txt)
- **LangChain Text Splitter** — RecursiveCharacterTextSplitter with UUID-based chunk IDs

### Cache Adapters (`app/infrastructure/cache.py`)
- `InMemoryCacheAdapter` — wraps LangChain's `InMemoryCache` (with maxsize support)
- `SQLiteCacheAdapter` — persistent SQLite-backed cache with TTL
- `SemanticCacheAdapter` — **hybrid**: exact-match (LangChain InMemoryCache) + semantic-match (cosine similarity)

### Ingestion Pipeline
- Orchestrates load → split → embed → store
- Supports JSON, Markdown, and Plain Text files

### RAG Pipeline
- Two-layer cache: exact → semantic → full pipeline
- **`answer_stream()`** for streaming responses
- Score filtering (min_score=0.15) for token reduction
- **Three-stage cascading retrieval** for synonym-aware question answering

### FastAPI Routes
- `GET /health` — Service health check
- `POST /ingest` — Ingest JSON/MD/TXT file
- `POST /chat` — Full answer
- `POST /chat/stream` — **Streaming SSE response**

### Configuration
- pydantic-settings with cache settings including semantic threshold
- Token optimization: chunk_size=512, top_k=3, min_score=0.15
- Query expansion and loose prompt flags (default: disabled)

### Scheduler Cron Job (`app/scheduler/`)
- JWT authentication with auto-refresh
- Paginated data fetching from Scraper API
- Job logic: fetch → save temp → ingest → cleanup
- Exponential backoff retry (60s, 120s, 240s, ... up to 5 attempts)
- Last-fetch log (`data/scheduler_log.json`)
- Configurable interval via `schedule` library

### Chunk IDs
- UUID-based: `chunk_{uuid4_hex[:12]}_{index}` — eliminates collision risk on re-ingestion

### Vector Store CRUD (Feature 1)
- `delete(ids)` — delete chunks by IDs
- `delete_by_metadata(key, value)` — delete chunks by metadata key-value
- `get_all_ids()` — list all chunk IDs
- `get_all_chunks()` — return all chunks with metadata

### Document Management (Feature 2)
- `GET /documents` — list all ingested documents with metadata
- `GET /documents/{id}` — get single document metadata
- `DELETE /documents/{id}` — delete document and its chunks from vector store
- SQLite-backed document metadata tracking (`data/document_metadata.db`)

### Admin Endpoints (Feature 3)
- `POST /admin/scheduler/run` — manually trigger scheduler job
- `GET /admin/scheduler/status` — get last fetch log
- `POST /admin/cache/clear` — clear all cache layers
- `GET /admin/stats` — system statistics (vector count, doc count, cache sizes)
- `size()` method added to all cache adapters for stats reporting

### Conversation History (Feature 4)
- `GET /conversations` — list all conversations
- `GET /conversations/{id}` — get single conversation with messages
- `POST /conversations` — create new conversation
- `PUT /conversations/{id}` — update conversation title/messages
- `DELETE /conversations/{id}` — delete conversation
- SQLite-backed conversation storage (`data/conversations.db`)

### Metrics/Monitoring (Feature 5)
- `GET /metrics` — Prometheus-style metrics endpoint
- Metrics: vector_store_count, document_count, conversation_count, cache sizes

### PDF Support (Feature 6)
- `PDFDocumentLoader` using PyMuPDF (fitz)
- One Document per page with page number metadata
- Registered in `AutoDocumentLoader` for `.pdf` files

### Chunk Metadata Coordination Fix (Feature 7)
- **Bug fixed**: `DELETE /documents/{id}` now uses `delete_by_metadata("original_filename", ...)` instead of `delete_by_metadata("source", ...)` which mismatched with loaders' `source: path.name`
- Ingestion pipeline injects both `original_filename` and `source_path` into every chunk's metadata
- Admin chunk APIs: `GET /admin/chunks`, `DELETE /admin/chunks/{chunk_id}` for direct chunk management
- Cleanup script: `scripts/cleanup_orphans.py` with `--dry-run` support

## What's Left to Build / Fix

### High Priority
- [ ] **Dockerfile** — needs `requirements.txt` sync with `pyproject.toml` (still uses `pip install -r requirements.txt` but project uses UV/pyproject.toml)
- [ ] **End-to-end integration test** — No test suite exists
- [ ] **Run cleanup script** — Run `scripts/cleanup_orphans.py` on existing ChromaDB data to remove orphaned chunks

### Medium Priority
- [ ] **Error handling in ChromaVectorStore** — `add()` now checks for None collection, but could be more robust

### Low Priority
- [ ] **Rate limiting** — No rate limiting on API endpoints
- [ ] **Authentication** — No API key protection on endpoints
- [ ] **Docker compose for scheduler** — Could be added as a separate service

## Known Issues
1. **OpenRouter free models may be rate-limited**
2. **Semantic cache is O(n)** — Linear scan of all entries. Fine for 500 entries, but may need optimization for larger caches
3. **Streaming response is synchronous for cache hits** — Full answer is buffered and yielded as one chunk
4. **Dockerfile uses requirements.txt** — But project uses UV/pyproject.toml; needs sync
5. **Orphaned chunks may exist** — Pre-fix, chunks were stored with `source: tmpXXX.pdf` but delete searched by full temp path → some orphaned chunks may remain in ChromaDB

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
| 2026-06-16 | AutoDocumentLoader with JSON, Markdown, Plain Text support | Multi-format ingestion flexibility |
| 2026-06-16 | UUID-based chunk IDs (`uuid.uuid4().hex[:12]`) | Eliminates collision risk on re-ingestion |
| 2026-06-16 | retrieval_min_score lowered from 0.25 → 0.15 | Catch more potentially relevant chunks |
| 2026-06-16 | LLM model changed to poolside/laguna-m.1:free | Free-tier model availability |
| 2026-06-23 | Chunk metadata bug fix: delete_by_metadata uses original_filename | Loaders set `source: path.name` but delete searched by full temp path |
| 2026-06-23 | `get_all_chunks()` added to VectorStorePort + ChromaVectorStore | Enables admin chunk listing and orphan cleanup |
| 2026-06-23 | Admin chunk APIs: GET/DELETE /admin/chunks | Direct chunk management for debugging |
| 2026-06-23 | scripts/cleanup_orphans.py created | Find and remove orphaned chunks |