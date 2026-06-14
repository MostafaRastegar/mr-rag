# Features Overview

## click for [QUICK START](./USAGE.md)
## click for [Reade Features](./FEATURES.md)

## 1. Core RAG Pipeline

**Retrieval-Augmented Generation** for intelligent question-answering over scraped data.

### Ingestion
```
JSON File → Load → Chunk → Embed → Store in ChromaDB
```
- Loads JSON files (supports `content` and `text` fields)
- Splits text using LangChain's RecursiveCharacterTextSplitter
- Generates embeddings via OpenRouter API
- Stores vectors in ChromaDB (Docker)

### Question Answering
```
Question → Embed → Search ChromaDB → Build Context → LLM → Answer
```
- Embeds user questions
- Retrieves top-K semantically similar chunks from ChromaDB
- Filters low-relevance chunks (score < 0.25)
- Builds context from filtered chunks
- Generates answer via OpenRouter LLM
- Returns answer with source citations and relevance scores

---

## 2. Multi-Layer Caching

Three independent cache tiers with different TTLs and backends.

| Layer | TTL | Cache Key | What It Caches |
|-------|-----|-----------|----------------|
| Embedding | 1 hour | Query text hash | Query → embedding vector |
| LLM | 24 hours | Serialized messages | Messages → LLM response |
| RAG Q&A | 24 hours | Question text + semantic similarity | Question → full answer |

### RAG Cache: Two Sub-Layers

```
Question
  → [Exact Match] identical text? → HIT → instant response
  → MISS:
    → Embedding API
    → [Semantic Match] similar question? (cosine ≥ 0.92) → HIT → ~1s response
    → MISS:
      → ChromaDB + LLM → cache result
```

**Cache Backends:**
- InMemoryCache — wraps LangChain's `InMemoryCache` (ephemeral, default)
- SQLiteCache — persistent across restarts with TTL

---

## 3. Streaming API

Server-Sent Events (SSE) for real-time token delivery.

```
POST /chat/stream
```
- First token appears in ~3-5 seconds
- Progressive display while LLM generates
- Cache works with streaming (cache hits return instantly)
- Uses `httpx.AsyncClient.stream()` to stream from OpenRouter SSE

---

## 4. Token Reduction

Optimizations to reduce LLM token consumption by ~70%.

| Setting | Before | After | Impact |
|---------|--------|-------|--------|
| `chunk_size` | 1024 | **512** | Smaller chunks = less text per chunk |
| `top_k` | 5 | **3** | Fewer chunks sent to LLM |
| `retrieval_min_score` | — | **0.25** | Filters irrelevant chunks |
| `chunk_overlap` | 200 | **100** | Reduced redundancy |

All settings are configurable via `.env` file.

---

## 5. Scheduler Cron Job

Automated data ingestion from an external Scraper API.

### Flow
```
Scheduler (every N minutes)
  → POST /api/v1/token/ → JWT token
  → GET /api/v1/messages/search/?page=1..N → all messages
  → Save to temp JSON file
  → Run IngestionPipeline (load → chunk → embed → store)
  → Log: timestamp, total documents, status
  → Delete temp file
```

### Features
- Configurable interval (default: 60 minutes)
- JWT authentication with auto-refresh
- Pagination support (automatic page 1..N)
- **Exponential backoff retry** on API failure (60s, 120s, 240s, ... up to 5 attempts)
- Temp file lifecycle: auto-created → auto-deleted after success
- Last-fetch log: `data/scheduler_log.json`

---

## 6. Architecture: Hexagonal (Ports & Adapters)

Clean separation between domain, application, infrastructure, and scheduler layers.

**6 Abstract Ports:**
- `EmbeddingPort` — generate embeddings
- `LLMPort` — generate text (standard + streaming)
- `VectorStorePort` — store/search vectors
- `DocumentLoaderPort` — load documents from sources
- `TextSplitterPort` — split documents into chunks
- `CachePort` — cache responses (with semantic lookup)

**Benefits:**
- Swap any component without changing other code
- Easy to test (mock ports)
- New providers implement existing interfaces