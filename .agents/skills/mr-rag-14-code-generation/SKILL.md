---
name: mr-rag-14-code-generation
description: Formatting conventions, type hints, imports, and naming rules
---

# mr-rag-14-code-generation

## Usage

Use this skill when writing new code in the mr-rag project to ensure consistency with project conventions for types, imports, logging, and docstrings.

## Steps

1. Use Python 3.10+ type hints (lowercase generics: `list[X]`, `dict[str, Any]`)
2. Use `X | None` not `Optional[X]` for optional types
3. Organize imports: standard library → third-party → application
4. Add docstrings to all modules, classes, and public methods
5. Use `logger = logging.getLogger(__name__)` for logging

## Type Hints

```python
# ✅ Correct
from collections.abc import AsyncGenerator
from typing import Any

def process(items: list[str]) -> dict[str, int]: ...
def maybe(value: str | None = None) -> str | None: ...
async def stream() -> AsyncGenerator[str, None]: ...

# ❌ Incorrect
from typing import List, Dict, Optional
def process(items: List[str]) -> Dict[str, int]: ...
def maybe(value: Optional[str] = None) -> Optional[str]: ...
```

## Import Order

```python
# 1. Standard library
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

# 2. Third-party
from fastapi import APIRouter, HTTPException

# 3. Application
from app.core.domain import Answer, Message, SearchResult
from app.core.exceptions import RetrievalError
from app.core.ports import CachePort, EmbeddingPort, LLMPort, VectorStorePort
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | snake_case | `chroma_vector_store.py` |
| Classes | PascalCase | `IngestionPipeline`, `OpenRouterLLM` |
| Methods | snake_case | `run()`, `answer_stream()` |
| Private members | `_` prefix | `self._embedding`, `_cache_embedding` |
| Constants | UPPER_CASE | `SYSTEM_PROMPT`, `MAX_RETRIES` |
| Port interfaces | `Port` suffix | `EmbeddingPort`, `VectorStorePort` |

## Logging

```python
logger = logging.getLogger(__name__)
logger.info("Human-readable message with %s", variable)
logger.warning("Something unexpected: %s", detail)
logger.error("Operation failed: %s", str(error))
logger.exception("Context message with stack trace")
```

## Docstrings

```python
"""
Module docstring describing the purpose of this module.
"""

class SomeClass:
    """
    Class docstring explaining responsibility.
    """
    
    def some_method(self, param: str) -> int:
        """
        Method docstring.
        
        Args:
            param: Description of parameter.
        
        Returns:
            Description of return value.
        
        Raises:
            SomeError: When something goes wrong.
        """
```

## Should / Should Not

✅ Do: Use `logger = logging.getLogger(__name__)` at module level
✅ Do: Add type hints to ALL function parameters and return types
✅ Do: Use `from e` when re-raising exceptions to preserve chain
✅ Do: Write docstrings for all modules, classes, and public methods
❌ Don't: Use wildcard imports (`from module import *`)
❌ Don't: Use `print()` for logging — always use `logging` module
❌ Don't: Leave unused imports or variables