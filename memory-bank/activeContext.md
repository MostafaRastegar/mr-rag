# Active Context

## Current Focus
**Medium-priority features completed** — Vector Store CRUD, Document Management, Admin Endpoints, Conversation History, Metrics/Monitoring, and PDF Support have all been implemented and merged to main.

## What Has Been Built

### Core RAG Pipeline
- [x] Hexagonal architecture with 6 port interfaces
- [x] Ingestion pipeline: load → split → embed → store
- [x] RAG pipeline: embed → search → generate
- [x] Direct HTTP OpenRouter API (no LangChain coupling)
- [x] LangChain RecursiveCharacterTextSplitter for chunking

### Document Loading (Multi-Format)
- [x] `AutoDocumentLoader` — dispatches by file extension
- [x] `JsonDocumentLoader` — LangChain JSONLoader with **auto-detection** of content field from priority key list (`content`, `text`, `body`, `description`, `article`, etc.) + fallback to longest string value
- [x] `MarkdownDocumentLoader` — LangChain MarkdownHeaderTextSplitter (splits by headings)
- [x] `TextDocumentLoader` — LangChain TextLoader
- [x] Supported formats: `.json`, `.md`, `.txt`
- [x] JSON structure normalization: wrapped keys (`{"data": [...]}`), list-of-strings, single strings all handled automatically
- [x] Temp-file strategy: normalised records written to temp file before JSONLoader processes them

### Caching (LangChain-based)
- [x] `InMemoryCacheAdapter` — wraps LangChain's `InMemoryCache` (with maxsize support)
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
- [x] `retrieval_min_score`: 0.15 (filter low-relevance chunks)

### Scheduler Cron Job
- [x] JWT authentication with auto-refresh
- [x] Paginated data fetching from Scraper API
- [x] Fetch → save temp → ingest → cleanup
- [x] Exponential backoff retry logic (60s, 120s, 240s, ...)
- [x] Last-fetch log (timestamp, count, status)
- [x] Configurable interval via `.env`

### Chunk IDs
- [x] UUID-based chunk IDs (`chunk_{uuid4_hex[:12]}_{index}`) — eliminates collision risk on re-ingestion

### Document Deletion Bug Fix (Chunk Metadata Coordination)
- [x] **Bug**: `DELETE /documents/{id}` used `delete_by_metadata("source", doc.source_path)` but loaders store `"source": path.name` (just filename, e.g. `tmpXXX.pdf`)
- [x] **Fix**: Changed to `delete_by_metadata("original_filename", doc.original_filename)` — ingestion pipeline already injects `original_filename` into every chunk's metadata
- [x] **`get_all_chunks()`** added to `VectorStorePort` interface and `ChromaVectorStore` implementation
- [x] **Admin Chunk APIs**: `GET /admin/chunks` (list all chunks with metadata), `DELETE /admin/chunks/{chunk_id}` (delete single chunk)
- [x] **Cleanup Script**: `scripts/cleanup_orphans.py` — finds and deletes chunks whose `original_filename` doesn't match any SQLite document; supports `--dry-run`

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
| 2026-06-14 | Three-stage cascading retrieval (Query Expansion + Loose Prompt) |
| 2026-06-16 | AutoDocumentLoader: multi-format support (JSON, Markdown, Plain Text) |
| 2026-06-16 | UUID-based chunk IDs to avoid collisions |
| 2026-06-16 | retrieval_min_score lowered from 0.25 → 0.15 |
| 2026-06-16 | LLM model changed to poolside/laguna-m.1:free |
| 2026-06-23 | Chunk metadata bug fix: delete_by_metadata now uses original_filename, not source_path |
| 2026-06-23 | Admin chunk APIs: GET /admin/chunks, DELETE /admin/chunks/{chunk_id} |
| 2026-06-23 | Cleanup script: scripts/cleanup_orphans.py (finds and deletes orphaned chunks) |

## New Features: Synonym-Aware Retrieval

### Three-Stage Cascade (final)
1. **Stage 1 — Normal Search**: embed → search → filter → generate
   - If cascade is enabled, `allow_low_score_fallback=False` → returns empty if all scores below `min_score`
   - `_is_low_relevance()` checks average score < 0.30 to trigger cascade
2. **Stage 2 — Query Expansion** (opt-in via `query_expansion_enabled`):
   - If Stage 1 returns no results or low-relevance results, LLM generates N alternative phrasings with synonyms
   - Each variant gets embedded and searched; results deduplicated by chunk ID
   - Early-stop when enough unique chunks collected
3. **Stage 3 — Loose Prompt** (opt-in via `loose_prompt_enabled`):
   - Always activates regardless of Stage 2 outcome (even if chunks were found)
   - Three sub-modes depending on context availability:
     - Context exists + loose → `SYSTEM_PROMPT_LOOSE`: "use context, supplement with own knowledge"
     - No context + loose → `SYSTEM_PROMPT_GENERAL`: "answer based on general knowledge"
     - Context exists + strict → `SYSTEM_PROMPT`: "answer based only on context" (original)

### Key Implementation Details
- **`_is_low_relevance()`** — static method, checks average score < 0.30
- **`_expand_query()`** — calls LLM with `QUERY_EXPANSION_PROMPT`, parses output line-by-line
- **`_search_with_expansion()`** — embeds each variant, searches, deduplicates, merges, re-sorts by score
- **`_search(allow_low_score_fallback)`** — new parameter to control whether low-score fallback is allowed
- **`SYSTEM_PROMPT_GENERAL`** — purely for no-context general knowledge answers
- **`SYSTEM_PROMPT_LOOSE`** — for context + supplement mode
- **`SYSTEM_PROMPT`** — original strict mode (unchanged)

### Configuration Flags (all default: `False`)
| Setting | Default | Description |
|---------|---------|-------------|
| `query_expansion_enabled` | `False` | Enable/disable query expansion when results are low-relevance |
| `query_expansion_count` | `3` | Number of alternative phrasings for LLM to generate |
| `loose_prompt_enabled` | `False` | Enable/disable relaxed system prompt (Stage 3) |

## Next Steps
- [ ] Dockerfile sync (requirements.txt vs pyproject.toml)
- [ ] Integration tests
- [ ] Run cleanup script on existing data to remove orphaned chunks
