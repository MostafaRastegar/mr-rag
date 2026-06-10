# Product Context

## Problem
Need an intelligent question-answering system that can search across data collected by a web scraper (JSON format). Manual search through large scraped datasets is impractical and inefficient.

## Solution
Use RAG architecture with three stages:
1. **Ingestion:** Read JSON → split into chunks (size=1024, overlap=200) → generate embeddings → store in ChromaDB
2. **Retrieval:** Embed user question → search ChromaDB for most semantically similar chunks
3. **Generation:** Build a prompt with retrieved chunks as context → call OpenRouter LLM → return answer with sources

## User Experience
- Simple REST API with two main endpoints:
  - `POST /ingest` — Load a JSON file, chunk, embed, and index it
  - `POST /chat` — Ask a question, get an answer with source citations
- Each answer includes source chunks and relevance scores
- `GET /health` endpoint for service monitoring

## Target Users
- Developers who want to deploy a self-hosted RAG system
- Users who need semantic search over scraped/collected data