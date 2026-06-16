# Project Brief

## Objective
Build a production-ready RAG (Retrieval-Augmented Generation) system that:
- Ingests JSON, Markdown, and Plain Text data from files or an external web scraper via a periodic cron scheduler
- Chunks text with optimized parameters
- Creates embeddings via OpenRouter API
- Stores vectors in ChromaDB (Docker)
- Answers questions with cached responses and semantic matching
- Supports streaming responses for long answers
- Three-stage cascading retrieval for synonym-aware question answering
- All orchestrated with Docker Compose

## Repository
- **Remote:** `git@github.com:MostafaRastegar/mr-rag.git`
- **Current Branch:** `develop`

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Web Framework | FastAPI |
| Vector DB | ChromaDB (Docker) |
| Embedding & LLM | OpenRouter API (direct HTTP via httpx) |
| Text Splitting | LangChain RecursiveCharacterTextSplitter |
| Document Loading | LangChain JSONLoader, MarkdownHeaderTextSplitter, TextLoader |
| Caching | LangChain InMemoryCache + Semantic Cache |
| Scheduling | `schedule` library (cron job) |
| Containerization | Docker Compose |
| Dependency Management | UV (pyproject.toml) |

## Current Status
- Full Hexagonal Architecture (Ports & Adapters) with clean separation
- SOLID principles applied throughout
- All modules implemented and tested
- Three-tier caching with semantic matching
- Streaming API support
- Scheduler cron job for automated data ingestion
- Token reduction optimizations applied
- Three-stage cascading retrieval (Query Expansion + Loose Prompt)
- Multi-format document loading (JSON, Markdown, Plain Text)
- UUID-based chunk IDs to avoid collisions