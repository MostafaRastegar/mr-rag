# Product Context

## Problem
Need an intelligent question-answering system that can search across data collected by a web scraper (JSON format) or other document formats (Markdown, Plain Text). Manual search through large scraped datasets is impractical. Additionally, the system must automatically fetch and ingest new data periodically without manual intervention.

## Solution
Use RAG architecture with three stages:

### 1. Ingestion
Read file (JSON/Markdown/Text) → split into optimized chunks → generate embeddings → store in ChromaDB

### 2. Retrieval
Embed user question → search ChromaDB → filter low-relevance chunks (min_score=0.15) → return top matches

### 3. Generation
Build context from retrieved chunks → call OpenRouter LLM → return answer with streaming support

### 4. Automated Scheduling
Periodically fetch data from external Scraper API → ingest → cleanup temp files

### 5. Cascading Retrieval (Synonym Support)
Three-stage cascade to handle questions with synonyms or out-of-context queries:
- Stage 1: Normal strict retrieval
- Stage 2: Query Expansion (re-phrase with synonyms)
- Stage 3: Loose Prompt (relax system prompt, allow general knowledge)

## User Experience

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/ingest` | Load a file (JSON/MD/TXT/PDF), chunk, embed, and index it |
| `POST` | `/chat` | Ask a question, get a complete answer |
| `POST` | `/chat/stream` | Ask a question, get a streaming (SSE) answer |
| `POST` | `/upload` | Upload a file and ingest it |
| `GET` | `/documents` | List all ingested documents |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `GET` | `/admin/chunks` | List all chunks with metadata |
| `DELETE` | `/admin/chunks/{id}` | Delete a single chunk by ID |
| `POST` | `/admin/scheduler/run` | Manually trigger scheduler |
| `GET` | `/admin/scheduler/status` | Get last fetch status |
| `POST` | `/admin/cache/clear` | Clear all caches |
| `GET` | `/admin/stats` | System statistics |

### Scheduler
```bash
python -m app.scheduler.runner
```
- Automatically fetches data from Scraper API
- Configurable interval (default: 60 minutes)
- Exponential backoff retry on API failures
- Logs last fetch timestamp and status

## Target Users
- Developers who want a self-hosted RAG system
- Users who need semantic search over scraped/collected data
- Teams needing automated data ingestion pipelines