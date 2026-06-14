---
name: mr-rag-13-testing-patterns
description: Unit and integration testing patterns for hexagonal architecture
---

# mr-rag-13-testing-patterns

## Usage

Use this skill when writing tests, mocking Ports, adding integration tests, or understanding the testing strategy for the mr-rag project.

## Steps

1. For unit tests: mock the Ports (interfaces), not concrete implementations
2. Test cache hit/miss flows separately
3. Test edge cases: empty results, malformed cache, API failures
4. Use `Mock` for synchronous methods, `AsyncMock` for async methods
5. For integration tests: use real infrastructure (ChromaDB) with fixture cleanup

## Mocking Ports for Unit Tests

```python
def test_answer_with_cache_hit():
    mock_embedding = Mock()
    mock_llm = Mock()
    mock_vector_store = Mock()
    mock_cache = Mock()
    mock_cache.lookup.return_value = '{"text": "cached answer"}'
    
    pipeline = RAGPipeline(
        embedding=mock_embedding,
        llm=mock_llm,
        vector_store=mock_vector_store,
        cache=mock_cache,
    )
    
    result = pipeline.answer("What is fesenjan?")
    assert result.text == "cached answer"
    mock_embedding.embed_query.assert_not_called()  # Cache hit
```

## Testing No Results

```python
def test_answer_with_no_results():
    mock_vector_store = Mock()
    mock_vector_store.search.return_value = []
    
    pipeline = RAGPipeline(
        embedding=Mock(),
        llm=Mock(),
        vector_store=mock_vector_store,
        cache=None,
    )
    
    result = pipeline.answer("Unknown topic")
    assert "couldn't find" in result.text.lower()
```

## Testing Async Streaming

```python
@pytest.mark.asyncio
async def test_answer_stream():
    mock_llm = AsyncMock()
    mock_llm.generate_stream.return_value = __aiter__(["token1", "token2"])
    
    pipeline = RAGPipeline(
        embedding=Mock(),
        llm=mock_llm,
        vector_store=Mock(),
        cache=None,
    )
    
    tokens = [token async for token in pipeline.answer_stream("Question")]
    assert tokens == ["token1", "token2"]
```

## Integration Test Fixture

```python
@pytest.fixture
def chroma_store():
    store = ChromaVectorStore()
    store.clear()
    yield store
    store.clear()
```

## Should / Should Not

✅ Do: Mock Ports, not concrete implementations
✅ Do: Test cache hit/miss flows separately
✅ Do: Test "no results" and error paths
✅ Do: Keep unit tests fast — no external dependencies
❌ Don't: Mock concrete adapter classes — mock the Port interface
❌ Don't: Skip edge cases (empty results, malformed cache, API failures)
❌ Don't: Make HTTP calls in unit tests