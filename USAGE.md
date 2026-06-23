# Usage Guide

## Prerequisites

- Python 3.13+
- Docker (for ChromaDB)
- OpenRouter API key (free tier available)

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone git@github.com:MostafaRastegar/mr-rag.git
cd mr-rag

# Create virtual environment and activate
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Copy and fill in the environment variables
cp .env.example .env
```

### 2. Configure `.env`

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2:free
LLM_MODEL=poolside/laguna-m.1:free
```

### 3. Start ChromaDB

```bash
docker compose up -d chromadb
```

### 4. Start the API Server

```bash
uvicorn app.main:app --reload --port 8080
```

The API is now available at `http://localhost:8080`. OpenAPI docs at `http://localhost:8080/docs`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/ingest` | Ingest a file (JSON/MD/TXT/PDF) → chunk → embed → store |
| `POST` | `/chat` | Ask a question, get a complete answer |
| `POST` | `/chat/stream` | Ask a question, get a streaming (SSE) answer |
| `POST` | `/upload` | Upload a file and ingest it (auto temp cleanup) |
| `GET` | `/documents` | List all ingested documents |
| `GET` | `/documents/{id}` | Get single document metadata |
| `DELETE` | `/documents/{id}` | Delete document + its chunks from ChromaDB |
| `GET` | `/conversations` | List all conversations |
| `GET` | `/conversations/{id}` | Get single conversation with messages |
| `POST` | `/conversations` | Create new conversation |
| `PUT` | `/conversations/{id}` | Update conversation title or messages |
| `DELETE` | `/conversations/{id}` | Delete conversation |
| `GET` | `/admin/chunks` | List all chunks with metadata |
| `DELETE` | `/admin/chunks/{id}` | Delete a single chunk by ID |
| `POST` | `/admin/scheduler/run` | Manually trigger scheduler |
| `GET` | `/admin/scheduler/status` | Last scheduler fetch log |
| `POST` | `/admin/cache/clear` | Clear all cache layers |
| `GET` | `/admin/stats` | System statistics (vector count, doc count, cache sizes) |
| `GET` | `/metrics` | Prometheus-style metrics |

---

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "ok",
  "vector_store_count": 47
}
```

---

### Ingest Data

Load a file (JSON, Markdown, PDF, or Plain Text), split it into chunks, embed, and store in ChromaDB.

```bash
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "data/recipes_1.json"}'
```

Response:
```json
{
  "status": "success",
  "chunks_ingested": 47
}
```

**Supported file formats:**

| Format | Extension | Loader | Description |
|--------|-----------|--------|-------------|
| JSON | `.json` | LangChain JSONLoader | List of objects with `content` or `text` field |
| Markdown | `.md` | MarkdownHeaderTextSplitter | Splits by headings (#, ##, ###, etc.) |
| PDF | `.pdf` | PyMuPDF (fitz) | One document per page with page metadata |
| Plain Text | `.txt` | LangChain TextLoader | Entire file as one document |

**JSON format example:**
```json
[
  {"content": "text content here", "title": "optional title"},
  {"content": "more text", "category": "food"}
]
```

---

### Chat (Full Response)

Ask a question and get a complete answer with sources.

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the recipe for fesenjan?"}'
```

Response:
```json
{
  "answer": "Fesenjan is a Persian stew made with...",
  "sources": [
    {
      "content": "مواد لازم فسنجون: یک کیلو مرغ، ۳۰۰ گرم گردو...",
      "metadata": {"title": "دستور پخت فسنجون"},
      "score": 0.84
    }
  ]
}
```

---

### Chat (Streaming)

Ask a question and receive tokens progressively via SSE.

```bash
curl -N -X POST http://localhost:8080/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the recipe for fesenjan?"}'
```

Output (progressive, character by character):
```
F
Fe
Fes
Fese
Fesen
Fesenj
...
```

**Note:** The `-N` flag disables curl's buffering for real-time display.

---

### Upload File

Upload a file via HTTP multipart. Automatically detects type by extension, saves to temp, ingests, and cleans up.

```bash
curl -X POST http://localhost:8080/upload \
  -F "file=@data/recipes_1.json"
```

Response:
```json
{
  "status": "success",
  "file_name": "recipes_1.json",
  "chunks_ingested": 47,
  "message": "فایل با موفقیت بارگذاری شد. 47 قطعه استخراج شد."
}
```

Supported formats: `.json`, `.md`, `.txt`, `.pdf`

---

### Document Management

List, inspect, and delete ingested documents.

```bash
# List all documents
curl http://localhost:8080/documents

# Get single document metadata
curl http://localhost:8080/documents/<doc-id>

# Delete document + its chunks from ChromaDB
curl -X DELETE http://localhost:8080/documents/<doc-id>
```

Response (list):
```json
{
  "total": 3,
  "documents": [
    {
      "id": "uuid-...",
      "filename": "tmpabc123.json",
      "original_filename": "recipes_1.json",
      "source_path": "/tmp/tmpabc123.json",
      "file_type": "json",
      "chunk_count": 47,
      "ingested_at": 1718000000.0
    }
  ]
}
```

---

### Admin: Chunk Management

Inspect and delete individual chunks directly in ChromaDB.

```bash
# List all chunks (id, text preview, full metadata)
curl http://localhost:8080/admin/chunks

# Delete a single chunk by ID
curl -X DELETE http://localhost:8080/admin/chunks/<chunk-id>
```

Useful for debugging orphaned chunks or manual cleanup.

---

### Admin: Scheduler Control

Manually trigger the scheduler job or check its status.

```bash
# Trigger scheduler now
curl -X POST http://localhost:8080/admin/scheduler/run

# Check last fetch status
curl http://localhost:8080/admin/scheduler/status
```

---

### Admin: Cache & Stats

```bash
# Clear all cache layers (embedding, LLM, RAG)
curl -X POST http://localhost:8080/admin/cache/clear

# System statistics
curl http://localhost:8080/admin/stats

# Prometheus-style metrics
curl http://localhost:8080/metrics
```

---

### Conversation History

Persist and retrieve chat conversations.

```bash
# List all conversations
curl http://localhost:8080/conversations

# Get single conversation with messages
curl http://localhost:8080/conversations/<conv-id>

# Create new conversation
curl -X POST http://localhost:8080/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "My Chat", "messages": [{"role": "user", "content": "Hello"}]}'

# Update conversation (title or messages)
curl -X PUT http://localhost:8080/conversations/<conv-id> \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title"}'

# Delete conversation
curl -X DELETE http://localhost:8080/conversations/<conv-id>
```

---

### Cleanup Orphaned Chunks

If chunks remain in ChromaDB after their source document was deleted (common before the metadata fix), use the cleanup script:

```bash
# Preview orphans without deleting
python -m scripts.cleanup_orphans --dry-run

# Delete all orphaned chunks
python -m scripts.cleanup_orphans
```

The script compares each chunk's `original_filename` against documents in SQLite and removes unmatched chunks.

---

## Cache Behavior

Test the caching yourself:

```bash
# First call — takes ~5-10s (cache miss → ChromaDB + LLM)
curl -s -X POST http://localhost:8080/chat \
  -d '{"question": "How to make fesenjan?"}'

# Second call — instant! (exact cache hit)
curl -s -X POST http://localhost:8080/chat \
  -d '{"question": "How to make fesenjan?"}'

# Similar question — ~1s (semantic cache hit, cosine similarity)
curl -s -X POST http://localhost:8080/chat \
  -d '{"question": "How do I cook fesenjan?"}'
```

---

## Scheduler (Automated Ingestion)

Periodically fetch data from an external Scraper API and ingest it automatically.

### Run the Scheduler

```bash
# In a separate terminal
python -m app.scheduler.runner
```

### Scheduler Configuration (`.env`)

```env
# Scraper API
SCRAPER_API_URL=https://your-scraper-api.com
SCRAPER_USERNAME=your-username
SCRAPER_PASSWORD=your-password

# Schedule
CRON_INTERVAL_MINUTES=60

# Retry on failure
MAX_RETRIES=5
RETRY_DELAY_SECONDS=60
```

### Check Scheduler Status

```bash
# Log file location
cat data/scheduler_log.json
```

Example output:
```json
{
  "last_fetch": "2026-06-10T12:30:00+00:00",
  "total_documents": 150,
  "status": "success"
}
```

---

## Configuration Reference

All settings are in `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL |
| `EMBEDDING_MODEL` | `nvidia/llama-nemotron-embed-vl-1b-v2:free` | Embedding model |
| `LLM_MODEL` | `poolside/laguna-m.1:free` | LLM model |
| `CHROMA_HOST` | `127.0.0.1` | ChromaDB host |
| `CHROMA_PORT` | `8000` | ChromaDB port |
| `APP_HOST` | `0.0.0.0` | App listen address |
| `APP_PORT` | `8080` | App listen port |
| `CHUNK_SIZE` | `512` | Text chunk size (characters) |
| `CHUNK_OVERLAP` | `100` | Chunk overlap |
| `TOP_K` | `3` | Number of chunks retrieved |
| `RETRIEVAL_MIN_SCORE` | `0.15` | Minimum relevance score |
| `CACHE_TYPE` | `memory` | Cache backend: `memory` or `sqlite` |
| `CACHE_SEMANTIC_ENABLED` | `true` | Enable semantic cache |
| `CACHE_SEMANTIC_THRESHOLD` | `0.92` | Semantic similarity threshold |
| `QUERY_EXPANSION_ENABLED` | `false` | Enable synonym-aware query expansion (Stage 2) |
| `QUERY_EXPANSION_COUNT` | `3` | Number of alternative phrasings to generate |
| `LOOSE_PROMPT_ENABLED` | `false` | Enable relaxed system prompt fallback (Stage 3) |
| `SCRAPER_API_URL` | — | External Scraper API URL |
| `SCRAPER_USERNAME` | — | Scraper API username |
| `SCRAPER_PASSWORD` | — | Scraper API password |
| `CRON_INTERVAL_MINUTES` | `60` | Scheduler interval |
| `MAX_RETRIES` | `5` | Max scheduler retries |
| `RETRY_DELAY_SECONDS` | `60` | Initial retry delay |

---

## Project Structure

```
mr-rag/
├── app/
│   ├── api/                    # FastAPI endpoints
│   │   ├── routes.py           # /health, /ingest, /chat, /chat/stream
│   │   └── schemas.py          # Pydantic request/response models
│   ├── core/                   # Domain layer (no external deps)
│   │   ├── domain.py           # Data classes
│   │   ├── exceptions.py       # Exception hierarchy
│   │   └── ports.py            # Abstract interfaces (6 ports)
│   ├── infrastructure/         # Adapters (external integrations)
│   │   ├── cache.py            # InMemoryCacheAdapter, SQLiteCacheAdapter, SemanticCacheAdapter
│   │   ├── chroma_vector_store.py  # ChromaDB CRUD + get_all_chunks()
│   │   ├── document_loader.py  # AutoDocumentLoader (JSON, Markdown, PDF, Plain Text)
│   │   ├── document_repository.py # SQLite document metadata
│   │   ├── conversation_repository.py # SQLite conversation history
│   │   ├── pdf_loader.py       # PyMuPDF-based PDF loader
│   │   ├── openrouter_embedding.py
│   │   ├── openrouter_llm.py
│   │   └── text_splitter.py    # UUID-based chunk IDs
│   ├── pipeline/               # Business logic
│   │   ├── ingestion.py        # Load → split → embed → store
│   │   └── rag.py              # Embed → search → generate (with cache + cascade)
│   ├── scheduler/              # Cron job
│   │   ├── config.py           # Scheduler settings
│   │   ├── auth.py             # JWT authentication
│   │   ├── client.py           # Scraper API client
│   │   ├── job.py              # Job logic
│   │   ├── logger.py           # Last-fetch log
│   │   └── runner.py           # Cron loop
│   ├── config.py               # App settings
│   └── main.py                 # FastAPI app + DI wiring
├── data/                       # JSON data files
├── memory-bank/                # Project documentation
├── scripts/
│   └── cleanup_orphans.py      # Orphaned chunk cleanup utility
├── FEATURES.md                 # Feature overview
├── USAGE.md                    # Usage guide
├── docker-compose.yml
└── pyproject.toml
```

---

## Cascading Retrieval (Synonym Support)

When enabled, the RAG pipeline uses a three-stage cascade to handle questions with synonyms or alternative phrasings.

### How It Works

```
Stage 1 — Normal Search (always runs)
  → embed query → search ChromaDB → filter by min_score
  → If results are high-relevance → use strict prompt → done
  → If results are empty or low-relevance (avg score < 0.30):
     │
     └─→ Stage 2 — Query Expansion (if enabled)
           → LLM generates N alternative phrasings with synonyms
           → Embed each variant → search → deduplicate → merge
           → If meaningful chunks found → use strict prompt → done
           │
           └─→ Stage 3 — Loose Prompt (if enabled)
                 → Context exists: SYSTEM_PROMPT_LOOSE (supplement with own knowledge)
                 → No context: SYSTEM_PROMPT_GENERAL (answer from general knowledge)
```

### Configuration

All three flags default to `false`, meaning the pipeline behaves **exactly like the original** unless you opt in.

```env
# In .env file:

# Stage 2: Query Expansion
QUERY_EXPANSION_ENABLED=true
QUERY_EXPANSION_COUNT=3

# Stage 3: Loose Prompt
LOOSE_PROMPT_ENABLED=true
```

### Example Usage

```bash
# Without cascade (both false) — synonym won't match
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "پروژه را چطور launch کنم"}'

# With cascade enabled — query expansion generates:
# "پروژه را چطور run کنم", "روش راه‌اندازی پروژه", etc.
# Then searches each variant and merges results
```

### Prompt Modes

| Mode | System Prompt | Context Available | Behavior |
|------|---------------|-------------------|----------|
| Strict (original) | `SYSTEM_PROMPT` | Yes | "Answer based only on the context" |
| Loose with context | `SYSTEM_PROMPT_LOOSE` | Yes | "Use context, supplement with own knowledge" |
| Loose no context | `SYSTEM_PROMPT_GENERAL` | No | "Answer based on your general knowledge" |

---

## Troubleshooting

### ChromaDB Connection Refused
```bash
# Ensure ChromaDB is running
docker ps | grep chromadb

# Start if not running
docker compose up -d chromadb

# Wait a few seconds for it to be ready
```

### OpenRouter API Errors
```bash
# Check your API key is set
grep OPENROUTER_API_KEY .env

# Free models may be rate-limited; try different models
# Set LLM_MODEL=openai/gpt-4o-mini in .env
```

### No Results Found
```bash
# First, ingest some data
curl -X POST http://localhost:8080/ingest \
  -d '{"file_path": "data/recipes_1.json"}'

# Then ask questions
curl -X POST http://localhost:8080/chat \
  -d '{"question": "your question here"}'