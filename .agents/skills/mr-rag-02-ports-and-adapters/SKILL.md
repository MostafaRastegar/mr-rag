 ---
name: mr-rag-02-ports-and-adapters
description: Contract-driven design with 6 abstract Ports and their Infrastructure adapters
---

# mr-rag-02-ports-and-adapters

## Usage

Use this skill when creating a new Port interface, implementing a new Adapter, swapping an external service provider, or understanding the Port/Adapter relationship in mr-rag.

## Steps

1. If adding a new Port: define interface in `app/core/ports.py` with ABC and @abstractmethod
2. Add any new domain models to `app/core/domain.py`
3. Add any new exceptions to `app/core/exceptions.py`
4. Implement the Port in `app/infrastructure/` as a new adapter class
5. Wire dependencies in `app/main.py`
6. Use the Port in Pipeline or API layer

## The 6 Ports

| Port | Key Methods | Adapter(s) |
|------|------------|------------|
| `EmbeddingPort` | `embed_query()`, `embed_documents()` | `OpenRouterEmbedding` |
| `VectorStorePort` | `add()`, `search()`, `count()` | `ChromaVectorStore` |
| `LLMPort` | `generate()`, `generate_stream()` | `OpenRouterLLM` |
| `CachePort` | `lookup()`, `update()`, `clear()`, `lookup_semantic()`, `update_semantic()` | `InMemoryCacheAdapter`, `SQLiteCacheAdapter`, `SemanticCacheAdapter` |
| `DocumentLoaderPort` | `load()` | `JsonDocumentLoader` (LangChain JSONLoader) |
| `TextSplitterPort` | `split()` | `LangChainTextSplitter` (LangChain RecursiveCharacterTextSplitter) |

## Adapter Template

```python
"""
Adapter for [purpose]. Implements [PortName].
"""
from app.core.ports import SomePort
from app.core.domain import SomeModel

class SomeAdapter(SomePort):
    def __init__(self, config_param: str) -> None:
        self._param = config_param
    
    def some_method(self, input: str) -> SomeModel:
        # Implementation here
        ...
```

## LangChain Priority

When adding a new adapter:
1. First check if LangChain (`langchain_core`, `langchain_community`, `langchain_text_splitters`) provides a suitable implementation
2. If found, wrap it behind the Port interface and convert results to domain models
3. Only write custom code when no LangChain component exists

Examples of LangChain usage:
- `JsonDocumentLoader` → `langchain_community.document_loaders.JSONLoader`
- `MarkdownDocumentLoader` → `langchain_text_splitters.MarkdownHeaderTextSplitter`
- `TextDocumentLoader` → `langchain_community.document_loaders.TextLoader`
- `LangChainTextSplitter` → `langchain_text_splitters.RecursiveCharacterTextSplitter`
- `InMemoryCacheAdapter` → `langchain_core.caches.InMemoryCache`
- `SQLiteCacheAdapter` → `langchain_community.cache.SQLiteCache`

## Should / Should Not

✅ Do: Name adapter classes descriptively (e.g., `ChromaVectorStore`)
✅ Do: Keep adapter files focused on a single external integration
✅ Do: Import Port interface: `from app.core.ports import XPort`
✅ Do: Check LangChain first before writing custom implementations
✅ Do: Wrap LangChain components behind Port interfaces to maintain hexagonal architecture
❌ Don't: Add business logic to an adapter
❌ Don't: Import infrastructure classes in Pipeline or Core code
