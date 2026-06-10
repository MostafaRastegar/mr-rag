# Project Brief

## Objective
Build a simple RAG (Retrieval-Augmented Generation) pipeline that:
- Reads JSON data from a web scraper
- Chunks text (size: 1024)
- Creates embeddings via OpenRouter API
- Stores vectors in ChromaDB (Docker)
- Provides a Chat API using OpenRouter LLM
- Everything orchestrated with Docker Compose

## Repository
- **Remote:** `git@github.com:MostafaRastegar/mr-rag.git`
- **Current Branch:** `develop`

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Web Framework | FastAPI |
| Vector DB | ChromaDB (Docker) |
| Embedding & LLM | OpenRouter API (direct HTTP via httpx, no LangChain coupling) |
| Text Splitting | LangChain RecursiveCharacterTextSplitter |
| Containerization | Docker Compose |
| Dependency Management | UV (pyproject.toml) |

## Current Status
- Architecture is fully Hexagonal (Ports & Adapters) with clean separation of concerns
- SOLID principles are applied throughout
- All modules (Core, Infrastructure, Pipeline, API) are implemented
- Application can be run with `uvicorn`
- Docker Compose includes ChromaDB service; app Dockerfile exists but references `requirements.txt` (needs sync with `pyproject.toml`)