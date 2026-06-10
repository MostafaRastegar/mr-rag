# System Patterns

## Architecture: Hexagonal (Ports & Adapters)

The project follows a strict hexagonal architecture with clean separation between domain, application, infrastructure, and scheduler layers.

```
┌──────────────────────────────────────────────────────────────┐
│                      API Layer                                │
│  app/main.py  →  app/api/routes.py  →  schemas.py            │
│  Endpoints: /health, /ingest, /chat, /chat/stream             │
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
│  document_loader.py       (implements DocLoaderPort)          │
│  text_splitter.py         (implements TextSplitterPort)       │
│  cache.py                 (implements CachePort)              │
└───────────────────────────┬──────────────────────────────────┘
                            │ defined in
┌───────────────────────────▼──────────────────────────────────┐
│                      Core Layer                               │
│  domain.py      — Data classes (Document, Chunk, SearchResult│
│                   Answer, Message)                            │
│  ports.py       — Abstract interfaces (6 Ports)              │
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

### 2. LangChain used for text splitting and cache
- `RecursiveCharacterTextSplitter` for robust chunking
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
- `retrieval_min_score`: 0.25 (filter low-relevance chunks)
- Result: ~70% reduction in LLM token consumption

### 7. Scheduler Cron Job
- Uses `schedule` library (lightweight, no system cron needed)
- JWT authentication with auto-refresh
- Paginated data fetching from Scraper API
- Exponential backoff retry (60s, 120s, 240s, ...)
- Temp file lifecycle: save → ingest → cleanup

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
JSON File → JsonDocumentLoader.load()
         → List[Document]
         → LangChainTextSplitter.split()
         → List[Chunk]
         → OpenRouterEmbedding.embed_documents()
         → List[List[float]]
         → ChromaVectorStore.add()
         → int (count)
```

### RAG Flow (with caching)
```
Question
→ [Exact Cache Check] → HIT → return cached Answer
→ MISS:
  → Embedding API (with own cache)
  → [Semantic Cache Check] → HIT → return cached Answer
  → MISS:
    → ChromaDB search (top_k=3)
    → Filter low-relevance (min_score=0.25)
    → Build context from filtered chunks
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