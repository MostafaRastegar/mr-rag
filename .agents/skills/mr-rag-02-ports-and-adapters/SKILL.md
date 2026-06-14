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
| `DocumentLoaderPort` | `load()` | `JsonDocumentLoader` |
| `TextSplitterPort` | `split()` | `LangChainTextSplitter` |

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

## Should / Should Not

✅ Do: Name adapter classes descriptively (e.g., `ChromaVectorStore`)
✅ Do: Keep adapter files focused on a single external integration
✅ Do: Import Port interface: `from app.core.ports import XPort`
❌ Don't: Add business logic to an adapter
❌ Don't: Import infrastructure classes in Pipeline or Core code