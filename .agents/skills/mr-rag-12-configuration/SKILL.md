---
name: mr-rag-12-configuration
description: Settings management with pydantic-settings and .env files
---

# mr-rag-12-configuration

## Usage

Use this skill when adding new configuration variables, modifying environment settings, or understanding how configuration flows through the application.

## Steps

1. Add the field to `Settings` class in `app/config.py` with a sensible default
2. Add the environment variable to `.env.example`
3. Access the setting via `from app.config import settings` and `settings.field_name`

## Settings Class

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "openai/text-embedding-ada-002"
    llm_model: str = "meta-llama/llama-3.3-70b-instruct"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    chunk_size: int = 512
    chunk_overlap: int = 100
    top_k: int = 3
    retrieval_min_score: float = 0.25
    cache_type: str = "memory"
    cache_db_path: str = "data/cache.db"
    cache_ttl_embedding: int = 3600
    cache_ttl_llm: int = 86400
    cache_maxsize: int = 10_000
    cache_semantic_enabled: bool = True
    cache_semantic_threshold: float = 0.92
    cache_semantic_maxsize: int = 500
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

## Environment Variable Mapping

Python field names are automatically converted to UPPER_CASE:
- `openrouter_api_key` → `OPENROUTER_API_KEY`
- `chunk_size` → `CHUNK_SIZE`
- `cache_semantic_threshold` → `CACHE_SEMANTIC_THRESHOLD`

## Adding a New Setting

```python
# 1. Add to Settings class
class Settings(BaseSettings):
    new_feature_enabled: bool = False
    new_feature_timeout: int = 30

# 2. Add to .env.example
# NEW_FEATURE_ENABLED=false
# NEW_FEATURE_TIMEOUT=30

# 3. Use in code
if settings.new_feature_enabled:
    ...
```

## Should / Should Not

✅ Do: Provide sensible defaults for every config value
✅ Do: Use `pydantic-settings` for type validation and env file loading
✅ Do: Document all settings in `.env.example`
❌ Don't: Hardcode configuration values that could vary between environments
❌ Don't: Use `os.getenv()` directly — always go through `Settings` class
❌ Don't: Store secrets in `.env.example` — only show placeholder values