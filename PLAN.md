# RAG System Implementation Plan

## Overview
Build a simple RAG (Retrieval-Augmented Generation) pipeline that:
- Ingests JSON data from a web scraper
- Chunks text (size: 1024)
- Creates embeddings via OpenRouter API
- Stores vectors in ChromaDB (Docker)
- Provides a Chat API using OpenRouter LLM
- Everything orchestrated with Docker Compose

## Architecture

```
Docker Compose
├── ChromaDB (port 8000) - Vector Database
└── Python App (FastAPI, port 8080)
    ├── Ingestion Pipeline
    │   ├── Read JSON → Chunk (1024) → Embed → Store in ChromaDB
    └── Chat Pipeline
        ├── Receive Question → Embed → Retrieve from ChromaDB → LLM → Respond
```

## Tech Stack
- **Language:** Python 3.11+
- **Web Framework:** FastAPI
- **Vector DB:** ChromaDB (Docker)
- **Framework:** LangChain
- **LLM & Embedding:** OpenRouter API
- **Orchestration:** Docker Compose

---

## Step-by-Step Implementation

### Step 1: Project Scaffolding
**Goal:** Create the project directory structure and configuration files.

**Files to create:**
- `docker-compose.yml` - Service definitions
- `Dockerfile` - Python app container
- `.env.example` - Environment variable template
- `.gitignore` - Ignore unnecessary files

**Verification:**
```bash
docker compose config  # Should parse without errors
```

---

### Step 2: Configuration & Dependencies
**Goal:** Set up Python dependencies and configuration module.

**Files to create:**
- `requirements.txt` - Python packages
- `app/config.py` - Centralized configuration (settings, API keys, model names)

**Key decisions:**
- Embedding model via OpenRouter: `openai/text-embedding-ada-002` (or `mistralai/mistral-embed`)
- LLM model via OpenRouter: `meta-llama/llama-3.3-70b-instruct` (or any preferred model)
- Chunk size: 1024
- Chunk overlap: 200

**Verification:**
```bash
pip install -r requirements.txt  # Should install without errors
python -c "from app.config import Settings; print('Config OK')"
```

---

### Step 3: Embedding Service Abstraction
**Goal:** Create a clean abstraction for OpenRouter embedding API following SOLID principles.

**SOLID applied:**
- **S** - Single Responsibility: This class only handles embedding
- **I** - Interface Segregation: Define a small, focused interface
- **D** - Dependency Inversion: Depend on abstractions, not implementations

**Files to create:**
- `app/embedding_service.py` - OpenRouter embedding client

**Verification:**
```bash
python -c "from app.embedding_service import EmbeddingService; print('Embedding Service OK')"
```

---

### Step 4: LLM Service Abstraction
**Goal:** Create a clean abstraction for OpenRouter LLM chat API.

**SOLID applied:**
- **S** - Single Responsibility: This class only handles LLM chat
- **O** - Open/Closed: Can add new LLM providers without modifying existing code
- **D** - Dependency Inversion: Depend on abstraction

**Files to create:**
- `app/llm_service.py` - OpenRouter LLM client

**Verification:**
```bash
python -c "from app.llm_service import LLMService; print('LLM Service OK')"
```

---

### Step 5: Ingestion Pipeline
**Goal:** Read scraper JSON output, chunk documents, embed, and store in ChromaDB.

**SOLID applied:**
- **S** - Single Responsibility: Each function/class has one job (read, chunk, embed, store)
- **O** - Open/Closed: New document sources can be added without changing pipeline core
- **L** - Liskov Substitution: Document sources implement the same interface

**Files to create:**
- `app/document_loader.py` - Load JSON from scraper
- `app/text_splitter.py` - Chunk documents (size=1024, overlap=200)
- `app/ingestion_pipeline.py` - Orchestrate the full ingestion workflow

**Verification:**
```bash
# Place a sample JSON file in data/ and run:
python -m app.ingestion_pipeline --input data/sample.json
# Should print: "Ingested N chunks successfully"
```

---

### Step 6: Vector Store Setup
**Goal:** Initialize ChromaDB and provide a clean repository layer for vector operations.

**SOLID applied:**
- **S** - Single Responsibility: Repository only handles DB operations
- **D** - Dependency Inversion: High-level code doesn't depend on ChromaDB directly

**Files to create:**
- `app/vector_store.py` - ChromaDB repository (add, search, delete)

**Verification:**
```bash
python -c "from app.vector_store import VectorStore; print('Vector Store OK')"
```

---

### Step 7: RAG Pipeline (Retrieval + Generation)
**Goal:** Chain together retrieval from ChromaDB and generation from OpenRouter LLM.

**SOLID applied:**
- **S** - Single Responsibility: RAG pipeline orchestrates, doesn't implement details
- **D** - Dependency Inversion: Depends on abstractions (EmbeddingService, LLMService, VectorStore)

**Files to create:**
- `app/rag_pipeline.py` - RAG orchestration (retrieve context, build prompt, generate answer)

**Verification:**
```bash
python -c "
from app.rag_pipeline import RAGPipeline
print('RAG Pipeline initialized successfully')
"
```

---

### Step 8: FastAPI Endpoints
**Goal:** Expose REST API for ingestion and chat.

**Files to create:**
- `app/main.py` - FastAPI application with two endpoints:
  - `POST /ingest` - Ingest a JSON file
  - `POST /chat` - Ask a question and get an answer

**SOLID applied:**
- **S** - Single Responsibility: Routes only handle HTTP, delegate business logic
- **D** - Dependency Inversion: Routes depend on service abstractions

**Verification:**
```bash
# Start the app:
uvicorn app.main:app --reload --port 8080

# Test endpoints:
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello, how are you?"}'
# Should return: {"answer": "...", "sources": [...]}
```

---

### Step 9: Docker Compose Integration
**Goal:** Containerize everything and verify end-to-end.

**Update:**
- `docker-compose.yml` - Ensure ChromaDB and app services work together
- `Dockerfile` - Finalize for production

**Verification:**
```bash
docker compose up -d
docker compose logs app  # Should show "Application startup complete"
curl http://localhost:8080/health  # Should return {"status": "ok"}
```

---

### Step 10: End-to-End Test
**Goal:** Run a complete test cycle: ingest → chat → verify.

**Verification:**
```bash
# 1. Ingest sample data
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "./data/recipes_1.json"}'

# 2. Ask a question
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What information do you have?"}'

# 3. Check ChromaDB collection count
curl http://localhost:8000/api/v1/collections/rag_docs/count
```

---

## File Structure (Final)

```
ai-rag/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── requirements.txt
├── PLAN.md
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI routes
│   ├── config.py            # Settings & configuration
│   ├── embedding_service.py # OpenRouter embedding abstraction
│   ├── llm_service.py       # OpenRouter LLM abstraction
│   ├── vector_store.py      # ChromaDB repository
│   ├── document_loader.py   # JSON document loader
│   ├── text_splitter.py     # LangChain text splitter config
│   ├── ingestion_pipeline.py # Ingestion orchestrator
│   └── rag_pipeline.py      # RAG orchestrator
└── data/
    └── sample.json          # Example scraper output
```

## SOLID Principles Applied

| Principle | Where Applied |
|-----------|---------------|
| **S** (Single Responsibility) | Each class has exactly one job |
| **O** (Open/Closed) | EmbeddingService/LLMService can be extended for new providers |
| **L** (Liskov Substitution) | All services implement consistent interfaces |
| **I** (Interface Segregation) | Small, focused interfaces (embed, chat, store, load) |
| **D** (Dependency Inversion) | High-level pipelines depend on abstractions, not concrete implementations |

## Clean Code Guidelines

1. **Naming:** Classes = nouns (`EmbeddingService`), Functions = verbs (`retrieve_context`)
2. **Small functions:** Each function does one thing
3. **Type hints:** All functions have type annotations
4. **No magic numbers:** Constants in `config.py`
5. **Error handling:** Custom exceptions with clear messages
6. **Logging:** Use `logging` module instead of `print`
7. **Comments:** Only when the "why" is not obvious