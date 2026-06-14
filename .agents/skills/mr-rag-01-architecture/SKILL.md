---
name: mr-rag-01-architecture
description: Architecture rules and hexagonal layering for the mr-rag project
---

# mr-rag-01-architecture

## Usage

Use this skill when working on project structure, adding new modules, refactoring layer boundaries, or understanding the dependency flow in the mr-rag project.

## Steps

1. Identify which layer the new code belongs to: Core, Infrastructure, Pipeline, API, or Scheduler
2. Verify that the new module imports only from layers below it (never above or sideways)
3. For Pipeline code: import only from `app.core.*`, never from `app.infrastructure.*`
4. For Infrastructure code: implement the relevant Port from `app.core.ports`
5. For API code: keep route handlers thin — validate, call pipeline, serialize response

## Layer Structure

```
┌──────────────────────────────────────────────────────────────┐
│                      API Layer                                │
│  app/main.py  →  app/api/routes.py  →  schemas.py            │
│  Endpoints: /health, /ingest, /chat, /chat/stream             │
└───────────────────────────┬──────────────────────────────────┘
                            │ depends on
┌───────────────────────────▼──────────────────────────────────┐
│                    Pipeline Layer                              │
│  app/pipeline/ingestion.py  — load → split → embed → store   │
│  app/pipeline/rag.py        — embed → search → generate      │
│  (depends ONLY on abstract ports)                             │
└───────────────────────────┬──────────────────────────────────┘
                            │ implements
┌───────────────────────────▼──────────────────────────────────┐
│                 Infrastructure Layer                           │
│  openrouter_embedding.py  (implements EmbeddingPort)           │
│  openrouter_llm.py        (implements LLMPort + streaming)   │
│  chroma_vector_store.py   (implements VectorStorePort)        │
│  document_loader.py       (implements DocLoaderPort)          │
│  text_splitter.py         (implements TextSplitterPort)       │
│  cache.py                 (implements CachePort)              │
└───────────────────────────┬──────────────────────────────────┘
                            │ defined in
┌───────────────────────────▼──────────────────────────────────┐
│                      Core Layer                               │
│  domain.py      — Data classes (Document, Chunk, SearchResult│
│                   Answer, Message)                            │
│  ports.py       — Abstract interfaces (6 Ports)              │
│  exceptions.py  — Custom exception hierarchy                 │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  Scheduler Layer (Standalone)                  │
│  app/scheduler/config.py   — Scheduler settings              │
│  app/scheduler/auth.py     — JWT authentication               │
│  app/scheduler/client.py   — Scraper API client               │
│  app/scheduler/job.py      — fetch → ingest → cleanup        │
│  app/scheduler/logger.py   — Last fetch log                   │
│  app/scheduler/runner.py   — Cron loop with schedule library  │
└──────────────────────────────────────────────────────────────┘
```

## Layer Rules

- Core Layer: Zero external dependencies, pure Python only
- Infrastructure Layer: Depends only on Core, implements Ports
- Pipeline Layer: Depends only on Core, uses Port interfaces
- API Layer: Thin handlers, translates domain exceptions to HTTP
- Scheduler Layer: Self-contained cron job, calls IngestionPipeline

## Should / Should Not

✅ Do: Use `from app.core.ports import X` in Pipeline and Infrastructure
✅ Do: Use `from app.core.domain import X` everywhere
❌ Don't: Import Infrastructure from Pipeline
❌ Don't: Import API from Pipeline
❌ Don't: Put business logic in route handlers