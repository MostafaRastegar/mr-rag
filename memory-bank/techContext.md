# Tech Context

## Technologies Used

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.13 (slim) | Runtime |
| FastAPI | ≥0.136.3 | Web framework |
| Uvicorn | (via fastapi[standard]) | ASGI server |
| ChromaDB | ≥1.5.9 | Vector database |
| httpx | ≥0.28.1 | HTTP client for OpenRouter API |
| LangChain | ≥1.3.4 | Text splitting only |
| langchain-chroma | ≥1.1.0 | ChromaDB client wrapper |
| langchain-text-splitters | (via langchain) | RecursiveCharacterTextSplitter |
| Pydantic | ≥2.13.4 | Data validation & schemas |
| pydantic-settings | ≥2.14.1 | Environment variable loading |
| python-multipart | ≥0.0.32 | Form data parsing |
| jq | ≥1.11.0 | JSON processing utility |

## Development Setup

### Environment Variables (`.env` file)
```
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2:free
LLM_MODEL=z-ai/glm-4.5-air:free
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
APP_HOST=0.0.0.0
APP_PORT=8080
```

### Running Locally
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Start ChromaDB
docker compose up -d chromadb

# 3. Run FastAPI app
uvicorn app.main:app --reload --port 8080
```

## Technical Constraints

### OpenRouter API
- Embedding endpoint: `POST {base_url}/embeddings`
- Chat completions endpoint: `POST {base_url}/chat/completions`
- Direct HTTP calls via `httpx` (not LangChain wrappers) due to compatibility issues
- Timeout set to 60 seconds for API calls
- Models are free-tier OpenRouter models by default

### ChromaDB
- Runs in Docker container with `network_mode: host`
- Uses cosine similarity (`hnsw:space: "cosine"`)
- Collection name: `rag_docs`
- Persistent storage mounted at `chroma_data` volume

### Chunking Configuration
- Chunk size: 1024 characters
- Chunk overlap: 200 characters
- Separators: `\n\n`, `\n`, ` `, `""` (from most to least preferred)

### Retrieval
- Top-K results: 5 chunks by default

## Dependency Management
- Uses **UV** package manager with `pyproject.toml`
- Dependencies listed under `[dependency-groups] dev`
- Dockerfile references `requirements.txt` (needs to be generated from `pyproject.toml` or updated)

## Deployment
- Docker Compose with two services:
  1. `chromadb` — Vector database (port 8000)
  2. `app` — FastAPI application (port 8080) — Dockerfile exists but needs `requirements.txt` sync
- Both services use `network_mode: host`