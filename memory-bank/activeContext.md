# Active Context

## Current Focus
**Documentation Complete** — All features implemented and memory bank fully updated.

## What Has Been Built

### Core RAG Pipeline
- [x] Hexagonal architecture with 6 port interfaces
- [x] Ingestion pipeline: load → split → embed → store
- [x] RAG pipeline: embed → search → generate
- [x] Direct HTTP OpenRouter API (no LangChain coupling)
- [x] LangChain RecursiveCharacterTextSplitter for chunking

### Caching (LangChain-based)
- [x] `InMemoryCacheAdapter` — wraps LangChain's `InMemoryCache`
- [x] `SQLiteCacheAdapter` — persistent SQLite with TTL
- [x] `SemanticCacheAdapter` — hybrid exact + semantic (cosine similarity)
- [x] Three-tier: embedding (1h), LLM (24h), RAG Q&A (24h)
- [x] Two RAG sub-layers: exact-match (hash) + semantic (cosine ≥ 0.92)

### Streaming
- [x] `POST /chat/stream` with SSE (Server-Sent Events)
- [x] `httpx.AsyncClient.stream()` for real-time token delivery
- [x] Cache works with streaming responses

### Token Reduction
- [x] `chunk_size`: 1024 → 512
- [x] `top_k`: 5 → 3
- [x] `retrieval_min_score`: 0.25 (filter low-relevance chunks)

### Scheduler Cron Job
- [x] JWT authentication with auto-refresh
- [x] Paginated data fetching from Scraper API
- [x] Fetch → save temp → ingest → cleanup
- [x] Exponential backoff retry logic (60s, 120s, 240s, ...)
- [x] Last-fetch log (timestamp, count, status)
- [x] Configurable interval via `.env`

## Architecture Overview

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌───────────┐
│  Client  │────▶│  FastAPI  │────▶│  RAG Pipeline │────▶│ ChromaDB  │
└──────────┘     │  Server   │     └──────────────┘     └───────────┘
                 └──────────┘     │  + Cache (3-tier)  │
                                  │  + Streaming        │
                                  │  + Score filter     │
                                  └────────────────────┘

┌────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Scraper   │────▶│  Scheduler   │────▶│  Ingestion       │
│  API       │     │  (cron)      │     │  Pipeline        │
└────────────┘     └──────────────┘     └──────────────────┘
                   JWT auth + retry      │
                   ↓                     ↓
                   data/scheduler_log    ChromaDB
```

## Key Metrics
| Metric | Value |
|--------|-------|
| First response (cache miss) | ~5-10s |
| First response (exact cache hit) | <50ms |
| First response (semantic cache hit) | ~1s |
| Streaming first token | ~3-5s |
| Token reduction | ~70% |
| Chunks per query | 1-3 (after filter) |

## Recent Changes
| Date | Change |
|------|--------|
| 2026-06-10 | Scheduler cron job implemented (`app/scheduler/*`) |
| 2026-06-10 | Token reduction: chunk_size=512, top_k=3, min_score=0.25 |
| 2026-06-10 | Streaming API: `POST /chat/stream` with SSE |
| 2026-06-10 | Semantic cache: hybrid exact + cosine similarity matching |
| 2026-06-10 | LangChain cache adapters: InMemoryCacheAdapter, SQLiteCacheAdapter |

## Next Steps
- [ ] Dockerfile sync (requirements.txt vs pyproject.toml)
- [ ] Integration tests
- [ ] UUID chunk IDs to avoid collisions
- [ ] Admin endpoints for scheduler: POST /scheduler/run, GET /scheduler/status