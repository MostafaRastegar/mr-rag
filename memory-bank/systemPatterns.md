# System Patterns

## Architecture: Hexagonal (Ports & Adapters)

The project follows a strict hexagonal architecture with clean separation between domain, application, infrastructure, and scheduler layers.

```
┌──────────────────────────────────────────────────────────────┐
│                      API Layer                                │
│  app/main.py  →  app/api/routes.py  →  schemas.py            │
│  Endpoints: /health, /ingest, /chat, /chat/stream,           │
│             /documents, /conversations, /admin/*, /metrics    │
└───────────────────────────┬──────────────────────────────────┘
                            │ depends on
┌───────────────────────────▼──────────────────────────────────┐
│                    Pipeline Layer                              │
│  app/pipeline/ingestion.py  — load → split → embed → store   │
│  app/pipeline/rag.py        — embed → search → generate      │
│  (depends ONLY on abstract ports)                             │
└───────────────────────────┬──────────────────────────────────┘
                            │ implements
┌───────────────────────────▼──────────────────────────────────┐
│                 Infrastructure Layer                          │
│  openrouter_embedding.py  (implements EmbeddingPort)          │
│  openrouter_llm.py        (implements LLMPort + streaming)   │
│  chroma_vector_store.py   (implements VectorStorePort)        │
│    — delete(), delete_by_metadata(), get_all_ids(),           │
│      get_all_chunks()                                         │
│  document_loader.py       (implements DocLoaderPort)          │
│    — AutoDocumentLoader: JSON, Markdown, PDF, Plain Text      │
│  text_splitter.py         (implements TextSplitterPort)       │
│    — UUID-based chunk IDs                                     │
│  cache.py                 (implements CachePort)              │
│    — InMemoryCacheAdapter, SQLiteCacheAdapter,                │
│      SemanticCacheAdapter (hybrid exact + semantic)           │
│  document_repository.py   (implements DocumentRepositoryPort) │
│    — SQLiteDocumentRepository                                 │
│  conversation_repository.py (implements ConversationRepoPort) │
│    — SQLiteConversationRepository                             │
└───────────────────────────┬──────────────────────────────────┘
                            │ defined in
┌───────────────────────────▼──────────────────────────────────┐
│                      Core Layer                               │
│  domain.py      — Data classes (Document, Chunk, SearchResult│
│                   Answer, Message, DocumentInfo,              │
│                   Conversation, ConversationMessage)          │
│  ports.py       — Abstract interfaces (8 Ports)              │
│  exceptions.py  — Custom exception hierarchy                 │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  Scheduler Layer (Standalone)                  │
│  app/scheduler/config.py   — Scheduler settings              │
│  app/scheduler/auth.py     — JWT authentication               │
│  app/scheduler/client.py   — Scraper API client               │
│  app/scheduler/job.py      — fetch → ingest → cleanup        │
│  app/scheduler/logger.py   — Last fetch log                   │
│  app/scheduler/runner.py   — Cron loop with schedule library  │
└──────────────────────────────────────────────────────────────┘
```

## Key Architecture Decisions

### 1. Direct HTTP for LLM/Embedding (no LangChain wrappers)
- OpenRouter API incompatible with some LangChain abstractions
- Using `httpx` directly for embedding and LLM endpoints
- Full control over request/response handling

### 2. LangChain used for text splitting, document loading, and cache
- `RecursiveCharacterTextSplitter` for robust chunking
- `JSONLoader` for JSON files, `MarkdownHeaderTextSplitter` for Markdown, `TextLoader` for plain text
- `InMemoryCache` from `langchain_core.caches` via `InMemoryCacheAdapter`
- All results converted to domain objects to avoid coupling

### 3. Manual Dependency Injection
- Dependencies wired explicitly in `app/main.py`
- Each pipeline receives dependencies through constructor injection
- No DI framework — keeps the graph explicit and traceable

### 4. Three-Tier Caching Architecture
```
Layer 1: Embedding Cache (TTL: 1h)
         — Caches query → embedding vector results

Layer 2: LLM Cache (TTL: 24h)
         — Caches messages → LLM response

Layer 3: RAG Q&A Cache (two sub-layers):
  a) Exact-match (SHA-256 hash)
     — Identical questions return instantly
  b) Semantic (cosine similarity ≥ 0.92)
     — Similar questions matched via embedding similarity
```

### 5. Streaming Support
- `POST /chat/stream` endpoint with SSE (Server-Sent Events)
- Uses `httpx.AsyncClient.stream()` for real-time token delivery
- First token displayed in ~3-5 seconds
- Cache still works on streaming responses

### 6. Token Reduction Strategy
- `chunk_size`: 1024 → 512 (smaller chunks)
- `top_k`: 5 → 3 (fewer chunks sent to LLM)
- `retrieval_min_score`: 0.15 (filter low-relevance chunks)
- Result: ~70% reduction in LLM token consumption

### 7. Scheduler Cron Job
- Uses `schedule` library (lightweight, no system cron needed)
- JWT authentication with auto-refresh
- Paginated data fetching from Scraper API
- Exponential backoff retry (60s, 120s, 240s, ...)
- Temp file lifecycle: save → ingest → cleanup

### 8. Multi-Format Document Loading
- `AutoDocumentLoader` dispatches by file extension
- JSON: LangChain JSONLoader with **auto-detection** of content field from priority key list (`content`, `text`, `body`, `description`, `article`, `markdown`, `html`, `summary`, `text_content`, `page_content`) + fallback to longest string value
- JSON structure normalization: wrapped keys (`{"data": [...]}`, `{"results": [...]}`, etc.), list-of-strings, and single strings all handled automatically via `_normalize_json_structure()`
- Temp-file strategy: normalised records written to a temporary file so JSONLoader always reads a consistent flat list of dicts
- Markdown: LangChain MarkdownHeaderTextSplitter (splits by headings)
- Plain Text: LangChain TextLoader
- Easy to extend with new formats by adding a new loader

### 9. UUID-Based Chunk IDs
- Format: `chunk_{uuid4_hex[:12]}_{index}`
- Eliminates collision risk on re-ingestion
- Prevents duplicate chunks in ChromaDB

### 10. Document Deletion via Metadata Coordination
- **Problem**: Loaders store `"source": path.name` (e.g. `tmpXXX.pdf`) in chunk metadata, but `DELETE /documents/{id}` was looking up by `doc.source_path` (full temp path `/tmp/tmpXXX.pdf`)
- **Fix**: Ingestion pipeline injects `"original_filename"` into every chunk's metadata; delete now matches on `original_filename`
- **Admin Chunk APIs**: `GET /admin/chunks` for inspection, `DELETE /admin/chunks/{chunk_id}` for targeted removal
- **Cleanup Script**: `scripts/cleanup_orphans.py` identifies chunks whose `original_filename` has no matching SQLite document

## SOLID Principles

| Principle | Implementation |
|-----------|---------------|
| **S** (Single Responsibility) | Each class has exactly one job |
| **O** (Open/Closed) | New providers added by implementing port interfaces |
| **L** (Liskov Substitution) | All adapters implement their port interface |
| **I** (Interface Segregation) | 6 small focused ports |
| **D** (Dependency Inversion) | Pipelines depend on abstract ports |

## Data Flow

### Ingestion Flow
```
File (JSON/MD/TXT) → AutoDocumentLoader.load()
         → List[Document]
         → LangChainTextSplitter.split()
         → List[Chunk] (UUID-based IDs)
         → OpenRouterEmbedding.embed_documents()
         → List[List[float]]
         → ChromaVectorStore.add()
         → int (count)
```

### RAG Flow (with caching + cascading retrieval)
```
Question
→ [Exact Cache Check] → HIT → return cached Answer
→ MISS:
  → Embedding API (with own cache)
  → [Semantic Cache Check] → HIT → return cached Answer
  → MISS:
    → Stage 1: ChromaDB search (top_k=3)
      → Filter low-relevance (min_score=0.15)
      → allow_low_score_fallback=False if cascade enabled
      → _is_low_relevance() if cascade enabled (avg < 0.30)
      → If no/low results + query_expansion_enabled=True:
        │
        └─→ Stage 2: Query Expansion
              → LLM generates N alternative phrasings (synonyms)
              → Embed each variant → search → deduplicate by chunk ID
              → Merge & re-sort by score
              → Early-stop when enough unique chunks
      │
      → If loose_prompt_enabled=True (Stage 3):
        ├─ Context exists → SYSTEM_PROMPT_LOOSE
        ├─ No context → SYSTEM_PROMPT_GENERAL
        └─ Context + strict → SYSTEM_PROMPT (original)
      │
      → LLM API (with own cache)
      → Store in both caches
      → return Answer (or stream via SSE)
```

### Scheduler Flow
```
Scheduler (every 60min)
  → POST /api/v1/token/ (JWT)
  → GET /api/v1/messages/search/?page=1...N
  → save_to_temp_file()
  → IngestionPipeline.run()
  → log_last_fetch()
  → delete_temp_file()
  → On error: retry with exponential backoff
```

## Error Handling Strategy
- **Domain layer:** Custom exception hierarchy (`RAGException` → specific)
- **Infrastructure layer:** Catches external errors, wraps in domain exceptions
- **Pipeline layer:** Catches and re-raises as pipeline exceptions
- **API layer:** Translates domain exceptions to HTTP responses
- **Scheduler layer:** Retry logic with backoff, logs errors to file