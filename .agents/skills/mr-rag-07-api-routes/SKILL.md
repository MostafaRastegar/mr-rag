---
name: mr-rag-07-api-routes
description: Endpoint patterns using factory function and thin handlers
---

# mr-rag-07-api-routes

## Usage

Use this skill when adding a new API endpoint, modifying existing routes, or adding request/response schemas.

## Steps

1. Add request/response schemas to `app/api/schemas.py` using Pydantic `BaseModel`
2. Add the endpoint to `create_router()` in `app/api/routes.py`
3. If the endpoint needs a new dependency, add it to `create_router()` parameters
4. Wire the new dependency in `app/main.py` and pass it to `create_router()`

## Route Factory Pattern

All routes are defined in `app/api/routes.py` using a factory function:

```python
def create_router(
    ingestion: IngestionPipeline,
    rag: RAGPipeline,
    vector_store: VectorStorePort,
) -> APIRouter:
    router = APIRouter()
    # ... endpoints ...
    return router
```

## Endpoint Template

```python
@router.post("/endpoint", response_model=ResponseSchema)
def endpoint_name(request: RequestSchema):
    """Docstring describing what this endpoint does."""
    
    # 1. Input validation
    if not request.field.strip():
        raise HTTPException(status_code=400, detail="Field cannot be empty")
    
    # 2. Call pipeline
    try:
        result = pipeline.run(request.field)
    except SomeDomainError as e:
        raise HTTPException(status_code=4xx, detail=str(e))
    except Exception as e:
        logger.exception("Contextual message")
        raise HTTPException(status_code=500, detail=f"Friendly message: {e}")
    
    # 3. Return serialized response
    return ResponseSchema(...)
```

## Should / Should Not

✅ Do: Keep route handlers thin — validation + pipeline call + serialization only
✅ Do: Use `response_model` for automatic response serialization
✅ Do: Translate domain exceptions to `HTTPException` with appropriate status codes
❌ Don't: Put business logic in route handlers
❌ Don't: Import infrastructure classes directly in routes
❌ Don't: Return raw domain objects — always use Pydantic schemas