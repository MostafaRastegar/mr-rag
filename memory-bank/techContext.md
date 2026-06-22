# Tech Context

## Technologies Used

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.13 (slim) | Runtime |
| FastAPI | ≥0.136.3 | Web framework |
| Uvicorn | (via fastapi[standard]) | ASGI server |
| ChromaDB | ≥1.5.9 | Vector database |
| httpx | ≥0.28.1 | HTTP client for OpenRouter & Scraper APIs |
| LangChain | ≥1.3.4 | Text splitting & cache |
| langchain-chroma | ≥1.1.0 | ChromaDB client wrapper |
| langchain-community | ≥0.4.2 | JSONLoader, TextLoader document loaders |
| langchain-classic | ≥1.0.7 | Legacy LangChain support |
| langchain-openai | ≥1.2.2 | OpenAI-compatible integration |
| jq | ≥1.11.0 | JSON query for document loader |
| schedule | ≥1.2.2 | Cron job scheduler |
| Pydantic | ≥2.13.4 | Data validation & schemas |
| pydantic-settings | ≥2.14.1 | Environment variable loading |
| python-multipart | ≥0.0.32 | Form data parsing |
| python-dotenv | ≥1.2.2 | .env file loading |
| PyMuPDF | ≥1.24.0 | PDF document loading |

## Project Structure

```
mr-rag/
├── app/
│   ├── __init__.py
│   ├── config.py              # App settings (models, chunking, cache)
│   ├── main.py                # FastAPI app, DI wiring
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py          # /health, /ingest, /chat, /chat/stream
│   │   └── schemas.py         # Pydantic request/response models
│   ├── core/
│   │   ├── __init__.py
│   │   ├── domain.py          # Document, Chunk, SearchResult, Answer, Message
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   └── ports.py           # 6 abstract interfaces
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── cache.py           # InMemoryCacheAdapter, SQLiteCacheAdapter, SemanticCacheAdapter
│   │   ├── chroma_vector_store.py  # ChromaDB CRUD
│   │   ├── document_loader.py # AutoDocumentLoader (JSON, Markdown, Plain Text)
│   │   ├── openrouter_embedding.py # Embedding API via httpx
│   │   ├── openrouter_llm.py       # LLM API + streaming via httpx
│   │   └── text_splitter.py   # LangChain RecursiveCharacterTextSplitter (UUID chunk IDs)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── ingestion.py       # Orchestrates load → split → embed → store
│   │   └── rag.py             # RAG with caching, streaming, token filtering, cascading retrieval
│   └── scheduler/
│       ├── __init__.py
│       ├── config.py          # Scheduler-specific settings
│       ├── auth.py            # JWT auth with auto-refresh
│       ├── client.py          # Scraper API client (pagination)
│       ├── job.py             # Job logic: fetch → ingest → cleanup + retry
│       ├── logger.py          # Last fetch log (timestamp, count, status)
│       └── runner.py          # Cron loop using schedule library
├── data/
│   └── recipes_*.json         # Example data files
├── memory-bank/               # Project documentation
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── FEATURES.md
├── USAGE.md
└── .env.example
```

## Development Setup

### Environment Variables (`.env` file)

```env
# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Models
EMBEDDING_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2:free
LLM_MODEL=poolside/laguna-m.1:free

# ChromaDB
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000

# App
APP_HOST=0.0.0.0
APP_PORT=8080

# Chunking (defaults in code, override in .env if needed)
# CHUNK_SIZE=512
# CHUNK_OVERLAP=100

# Retrieval (defaults in code, override in .env if needed)
# TOP_K=3
# RETRIEVAL_MIN_SCORE=0.15

# Cache (defaults in code, override in .env if needed)
# CACHE_TYPE=memory          # "memory" or "sqlite"
# CACHE_SEMANTIC_ENABLED=true
# CACHE_SEMANTIC_THRESHOLD=0.92

# Query Expansion (Stage 2)
# QUERY_EXPANSION_ENABLED=true
# QUERY_EXPANSION_COUNT=3

# Loose Prompt (Stage 3)
# LOOSE_PROMPT_ENABLED=true

# Scheduler (defaults in code, override in .env if needed)
# SCRAPER_API_URL=https://scraper.example.com
# SCRAPER_USERNAME=...
# SCRAPER_PASSWORD=...
# CRON_INTERVAL_MINUTES=60
# MAX_RETRIES=5
# RETRY_DELAY_SECONDS=60
```

### Running Locally

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Start ChromaDB
docker compose up -d chromadb

# 3. Run FastAPI app
uvicorn app.main:app --reload --port 8080

# 4. Run Scheduler (separate terminal)
python -m app.scheduler.runner
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/ingest` | Ingest a file (JSON/MD/TXT) → chunk → embed → store |
| `POST` | `/chat` | Answer a question (full response) |
| `POST` | `/chat/stream` | Answer a question (streaming SSE) |

### Example: Ingest Data
```bash
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "data/recipes_1.json"}'
```

### Example: Chat
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the recipe for fesenjan?"}'
```

### Example: Streaming Chat
```bash
curl -N -X POST http://localhost:8080/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the recipe for fesenjan?"}'
```

## Technical Constraints

### OpenRouter API
- Embedding: `POST {base_url}/embeddings`
- Chat completions: `POST {base_url}/chat/completions`
- Direct HTTP via `httpx` (not LangChain wrappers)
- Timeout: 60s (standard), 120s (streaming)
- Free-tier models by default

### ChromaDB
- Docker with `network_mode: host`
- Cosine similarity (`hnsw:space: "cosine"`)
- Collection: `rag_docs`
- Persistent volume: `chroma_data`

### Caching
- Three tiers: embedding (1h TTL), LLM (24h TTL), RAG Q&A (24h TTL)
- Two sub-layers for RAG: exact-match + semantic (cosine ≥ 0.92)
- Backends: InMemoryCache (LangChain) or SQLite (persistent)
- Semantic cache max: 500 entries, O(n) scan

### Token Optimization
- Chunk size: 512 chars (was 1024)
- Chunk overlap: 100 chars (was 200)
- Top-K: 3 chunks (was 5)
- Min relevance score: 0.15 (was 0.25, filters low-match chunks)
- Estimated saving: ~70% fewer LLM tokens

### Document Loading
- AutoDocumentLoader dispatches by file extension
- JSON: LangChain JSONLoader with jq schema (`.[]` selector)
- Markdown: LangChain MarkdownHeaderTextSplitter (splits by #, ##, ###, etc.)
- Plain Text: LangChain TextLoader
- Supported extensions: `.json`, `.md`, `.txt`

### Chunk IDs
- UUID-based: `chunk_{uuid4_hex[:12]}_{index}`
- Prevents collisions on re-ingestion
- Unique per chunk within a batch

### Scheduler
- `schedule` library (lightweight, Python-only)
- JWT auto-refresh (23h cache)
- Pagination: automatic page 1..N
- Retry: exponential backoff (60s, 120s, 240s, ...) up to 5 attempts
- Temp files: auto-deleted after successful ingest
- Log: `data/scheduler_log.json`

### Docker
- ChromaDB service with persistent volumes
- App Dockerfile exists (needs `requirements.txt` sync with `pyproject.toml`)
- Both services share a custom bridge network (`app_network`) for inter-container DNS resolution
- `CHROMA_HOST=chromadb` overrides `.env` value when running via Docker Compose
- `depends_on` with `condition: service_healthy` ensures ChromaDB is ready before app starts
- Ports `8000` and `8080` are exposed to host for local browser access
- Base image: `hub.hamdocker.ir/python:3.13-slim`
