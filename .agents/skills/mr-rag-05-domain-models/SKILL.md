---
name: mr-rag-05-domain-models
description: Core data classes with zero external dependencies
---

# mr-rag-05-domain-models

## Usage

Use this skill when adding or modifying domain models in `app/core/domain.py`, or when you need to understand the data structures flowing through the system.

## Steps

1. Add new fields with appropriate type hints and sensible defaults
2. Use `@dataclass` with `field(default_factory=...)` for mutable defaults
3. Keep models pure — no external library types, no business logic
4. Never import domain models from external packages

## Domain Models

### Document
```python
@dataclass
class Document:
    """A raw document loaded from an external source (e.g., JSON file)."""
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Chunk
```python
@dataclass
class Chunk:
    """A chunk of text produced by splitting a Document."""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""
```

### SearchResult
```python
@dataclass
class SearchResult:
    """A single result from a vector store search."""
    chunk: Chunk
    score: float = 0.0
```

### Answer
```python
@dataclass
class Answer:
    """The final answer produced by the RAG pipeline."""
    text: str
    sources: list[SearchResult] = field(default_factory=list)
```

### Message
```python
@dataclass
class Message:
    """A single message in a chat conversation."""
    role: str  # "system", "user", "assistant"
    content: str
```

## Should / Should Not

✅ Do: Use `str | None` for optional fields
✅ Do: Use `field(default_factory=dict)` for dict fields
✅ Do: Add type hints to every field
❌ Don't: Import from external packages (pydantic, langchain, etc.)
❌ Don't: Add business logic methods to domain classes
❌ Don't: Use mutable default values directly