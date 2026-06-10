# System Patterns

## Architecture: Hexagonal (Ports & Adapters)

The project follows a strict hexagonal architecture with clean separation between domain, application, and infrastructure layers.

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Layer                      │
│  app/main.py  →  app/api/routes.py  →  schemas.py   │
└──────────────────────┬──────────────────────────────┘
                        │ depends on
┌──────────────────────▼──────────────────────────────┐
│                 Pipeline Layer                       │
│  app/pipeline/ingestion.py                          │
│  app/pipeline/rag.py                                │
│  (depends ONLY on abstract ports)                   │
└──────────────────────┬──────────────────────────────┘
                        │ implements
┌──────────────────────▼──────────────────────────────┐
│              Infrastructure Layer                    │
│  openrouter_embedding.py  (implements EmbeddingPort) │
│  openrouter_llm.py        (implements LLMPort)      │
│  chroma_vector_store.py   (implements VectorStorePort)│
│  document_loader.py      (implements DocLoaderPort) │
│  text_splitter.py        (implements TextSplitterPort)│
│  cache.py                (implements CachePort)     │
└──────────────────────┬──────────────────────────────┘
                        │ defined in
┌──────────────────────▼──────────────────────────────┐
│                 Core Layer                           │
│  domain.py      — Pure data classes (Document,       │
│                    Chunk, SearchResult, Answer,       │
│                    Message)                          │
│  ports.py       — Abstract interfaces (Ports)        │
│                    including CachePort               │
│  exceptions.py  — Custom exception hierarchy         │
└─────────────────────────────────────────────────────┘
```

## Key Architecture Decisions

### 1. Direct HTTP calls instead of LangChain's LLM/Embedding wrappers
- OpenRouter's API is incompatible with some LangChain abstractions
- Using `httpx` directly for API calls to embedding and LLM endpoints
- More control over request/response handling
- Simpler error handling and logging

### 2. LangChain used ONLY for text splitting and cache infrastructure
- `RecursiveCharacterTextSplitter` provides robust chunking
- Results are converted to domain `Chunk` objects to avoid LangChain coupling
- `InMemoryCache` from `langchain_core.caches` used via `InMemoryCacheAdapter` wrapper
- Cache adapters provide clean domain port interface while leveraging LangChain internals

### 3. Manual Dependency Injection (no DI framework)
- Dependencies are wired explicitly in `app/main.py`
- Routes are created via a factory function `create_router()`
- Each pipeline receives its dependencies through constructor injection
- Keeps the dependency graph explicit and easy to trace

### 4. ChromaDB via langchain-chroma
- `langchain-chroma` provides a robust ChromaDB client
- Accessed at the collection level through `_collection` property
- Avoids LangChain's `Document` coupling by working with raw collections

### 5. Three-tier caching architecture
- **Embedding cache**: caches individual query → embedding vector results (TTL: 1h)
- **LLM cache**: caches messages → LLM response results (TTL: 24h)
- **RAG cache**: caches full question → answer results, skipping entire pipeline (TTL: 24h)
- In-memory (ephemeral) or SQLite (persistent) backends, configurable via `cache_type`

## SOLID Principles Applied

| Principle | Implementation |
|-----------|---------------|
| **S** (Single Responsibility) | Each class has exactly one job: `OpenRouterEmbedding` only embeds, `JsonDocumentLoader` only loads, `InMemoryCacheAdapter` only caches, etc. |
| **O** (Open/Closed) | New LLM/embedding/cache providers can be added by implementing the existing port interfaces |
| **L** (Liskov Substitution) | All adapters implement their port interface consistently; pipelines work with any implementation |
| **I** (Interface Segregation) | Six small focused ports: `EmbeddingPort`, `LLMPort`, `VectorStorePort`, `DocumentLoaderPort`, `TextSplitterPort`, `CachePort` |
| **D** (Dependency Inversion) | High-level pipelines depend on abstract ports, not concrete implementations |

## Data Flow

### Ingestion Flow
```
JSON File → JsonDocumentLoader.load()
         → List[Document]
         → LangChainTextSplitter.split()
         → List[Chunk]
         → OpenRouterEmbedding.embed_documents()
         → List[List[float]]
         → ChromaVectorStore.add()
         → int (count)
```

### Chat/RAG Flow (with caching)
```
Question (str)
→ [Cache Check] → HIT → return cached Answer immediately
→ MISS:
  → OpenRouterEmbedding.embed_query()  [checks own cache]
  → List[float] (query embedding)
  → ChromaVectorStore.search()
  → List[SearchResult]
  → RAGPipeline._build_context()
  → str (context)
  → OpenRouterLLM.generate()  [checks own cache]
  → str (answer)
  → store in RAG cache
  → return Answer
```

## Error Handling Strategy
- **Domain layer:** Custom exception hierarchy (`RAGException` → specific exceptions)
- **Infrastructure layer:** Catches external errors (HTTP, DB), wraps in domain exceptions
- **Pipeline layer:** Catches and re-raises as pipeline-specific exceptions
- **API layer:** Translates domain exceptions to HTTP responses with appropriate status codes