# Project Brief

## Objective
Build a production-ready RAG (Retrieval-Augmented Generation) system that:
- Ingests JSON data from an external web scraper via a periodic cron scheduler
- Chunks text with optimized parameters
- Creates embeddings via OpenRouter API
- Stores vectors in ChromaDB (Docker)
- Answers questions with cached responses and semantic matching
- Supports streaming responses for long answers
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