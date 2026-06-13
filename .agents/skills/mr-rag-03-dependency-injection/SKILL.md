---
name: mr-rag-03-dependency-injection
description: Manual dependency injection wiring in app/main.py
---

# mr-rag-03-dependency-injection

## Usage

Use this skill when wiring a new service into the application, adding a new dependency to an existing class, or understanding how dependencies flow through the mr-rag system.

## Steps

1. Create the Cache adapter (first tier of dependencies)
2. Create Infrastructure adapters (pass caches where needed)
3. Create Pipeline instances (pass infrastructure adapters as Port types)
4. Create API router (pass pipelines)
5. Include router in FastAPI app

## Wiring Flow

All dependencies are wired manually in `app/main.py`:

```python
# Step 1: Cache adapters
_cache_embedding: CachePort = InMemoryCacheAdapter(maxsize=settings.cache_maxsize)
_cache_llm: CachePort = InMemoryCacheAdapter(maxsize=settings.cache_maxsize)
_cache_rag: CachePort = SemanticCacheAdapter(
    maxsize=settings.cache_semantic_maxsize,
    default_threshold=settings.cache_semantic_threshold,
)

# Step 2: Infrastructure adapters
embedding = OpenRouterEmbedding(cache=_cache_embedding)
llm = OpenRouterLLM(cache=_cache_llm)
vector_store = ChromaVectorStore()
document_loader = JsonDocumentLoader()
text_splitter = LangChainTextSplitter()

# Step 3: Pipeline instances
ingestion_pipeline = IngestionPipeline(
    loader=document_loader,
    splitter=text_splitter,
    embedding=embedding,
    vector_store=vector_store,
)
rag_pipeline = RAGPipeline(
    embedding=embedding,
    llm=llm,
    vector_store=vector_store,
    cache=_cache_rag,
)

# Step 4: API router
app.include_router(
    create_router(
        ingestion=ingestion_pipeline,
        rag=rag_pipeline,
        vector_store=vector_store,
    )
)
```

## Constructor Injection Pattern

```python
class SomePipeline:
    def __init__(
        self,
        port1: Port1Type,
        port2: Port2Type,
        optional_port: OptionalPortType | None = None,
    ) -> None:
        self._port1 = port1
        self._port2 = port2
        self._optional_port = optional_port
```

## Should / Should Not

✅ Do: Wire all dependencies in `app/main.py` — one central location
✅ Do: Use Port types for constructor parameters
✅ Do: Keep initialization order: Cache → Infrastructure → Pipeline → Router
❌ Don't: Instantiate dependencies inside a class (e.g., `self._store = ChromaVectorStore()`)
❌ Don't: Use service locators or global DI containers