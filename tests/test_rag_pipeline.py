"""
Tests for the RAG pipeline's retrieval-quality behavior.

Ports are mocked per the project's testing conventions — no network calls and
no real vector store. These tests lock in the fixes that matter most:

  1. The loose prompt must NOT fire when good context was retrieved.
  2. Reranking must narrow the candidate pool and survive failures.
  3. Context must cite human-readable sources, not /tmp paths.
  4. Prompt selection must be driven by context relevance.
"""

from unittest.mock import Mock

import pytest

from app.core.domain import Chunk, SearchResult
from app.pipeline.rag import RAGPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(
    text: str, score: float, chunk_id: str = "", **metadata
) -> SearchResult:
    """Build a SearchResult for tests."""
    return SearchResult(
        chunk=Chunk(text=text, metadata=dict(metadata), id=chunk_id), score=score
    )


def make_pipeline(
    results: list[SearchResult] | None = None,
    reranker=None,
    retriever=None,
    llm_text: str = "ANSWER",
) -> RAGPipeline:
    """Build a RAGPipeline with mocked ports."""
    embedding = Mock()
    embedding.embed_query.return_value = [0.1, 0.2, 0.3]

    llm = Mock()
    llm.generate.return_value = llm_text

    vector_store = Mock()
    vector_store.search.return_value = results or []

    return RAGPipeline(
        embedding=embedding,
        llm=llm,
        vector_store=vector_store,
        cache=None,
        reranker=reranker,
        retriever=retriever,
    )


# ---------------------------------------------------------------------------
# Loose-prompt gating (the main cause of vague answers)
# ---------------------------------------------------------------------------


def test_loose_prompt_not_used_when_context_is_relevant():
    """
    With strong context, the strict grounded prompt must be used.

    Regression guard: previously the loose prompt fired whenever the flag was
    enabled, letting the model answer from general knowledge even when good
    context existed — the root cause of generic answers.
    """
    results = [make_result("detailed doc text", 0.85, "c1", original_filename="a.txt")]
    pipeline = make_pipeline(results=results)

    ctx = pipeline._prepare_rag("a question", None)
    system_message = ctx.messages[0].content

    assert "STRICTLY" in system_message
    assert "general knowledge" not in system_message


def test_loose_prompt_used_when_no_context():
    """With no context, the loose prompt is appropriate."""
    pipeline = make_pipeline(results=[])

    assert pipeline._should_use_loose_prompt([]) is True


def test_should_use_loose_prompt_threshold_behavior():
    """Weak context triggers the loose prompt; strong context does not."""
    pipeline = make_pipeline()

    weak = [make_result("t", 0.05, "c1")]
    strong = [make_result("t", 0.90, "c1")]

    assert pipeline._should_use_loose_prompt(weak) is True
    assert pipeline._should_use_loose_prompt(strong) is False


# ---------------------------------------------------------------------------
# Reranking
# ---------------------------------------------------------------------------


def test_rerank_keeps_top_n_and_reorders():
    """The reranker's order and cut-off are respected."""
    results = [make_result(f"chunk {i}", 0.9 - i * 0.1, f"c{i}") for i in range(10)]

    reranker = Mock()
    # Reranker prefers the last chunk.
    reranker.rerank.return_value = [
        SearchResult(chunk=results[9].chunk, score=0.95),
        SearchResult(chunk=results[3].chunk, score=0.80),
    ]

    pipeline = make_pipeline(results=results, reranker=reranker)
    out = pipeline._rerank("q", results)

    assert len(out) == 2
    assert out[0].chunk.id == "c9"
    assert out[1].chunk.id == "c3"


def test_rerank_failure_falls_back_to_retrieval_order():
    """A reranker exception must not break answering."""
    results = [make_result(f"chunk {i}", 0.9 - i * 0.1, f"c{i}") for i in range(8)]

    reranker = Mock()
    reranker.rerank.side_effect = RuntimeError("rerank API down")

    pipeline = make_pipeline(results=results, reranker=reranker)
    out = pipeline._rerank("q", results)

    # Original retrieval order preserved for the kept prefix.
    assert out[0].chunk.id == "c0"
    assert out[1].chunk.id == "c1"


def test_rerank_empty_result_falls_back():
    """An empty reranker response falls back instead of returning nothing."""
    results = [make_result(f"chunk {i}", 0.5, f"c{i}") for i in range(5)]

    reranker = Mock()
    reranker.rerank.return_value = []

    pipeline = make_pipeline(results=results, reranker=reranker)
    out = pipeline._rerank("q", results)

    assert len(out) >= 1


def test_rerank_skipped_without_reranker():
    """No reranker configured means retrieval order is preserved up to top_n."""
    from app.config import settings

    results = [make_result(f"chunk {i}", 0.9 - i * 0.1, f"c{i}") for i in range(8)]

    pipeline = make_pipeline(results=results)
    out = pipeline._rerank("q", results)

    assert len(out) == settings.rerank_top_n
    # Original retrieval order preserved.
    assert [r.chunk.id for r in out] == ["c0", "c1", "c2", "c3", "c4"]


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def test_build_context_uses_human_readable_source():
    """
    Context citations must use the original filename, not the temp path.

    Chunks are ingested from temp files, so `source` can be `/tmp/tmpXXXX.txt`.
    Showing that to the model is meaningless and produced confusing citations.
    """
    results = [
        make_result(
            "body text",
            0.8,
            "c1",
            source="/tmp/tmpabc123.txt",
            original_filename="final report.txt",
            page=3,
        )
    ]

    context = RAGPipeline._build_context(results)

    assert "final report.txt" in context
    assert "/tmp/" not in context
    assert "[1]" in context
    assert "p.3" in context


def test_build_context_numbers_sequentially():
    """Each chunk gets an ascending citation number."""
    results = [
        make_result("first", 0.9, "c1", original_filename="a.txt"),
        make_result("second", 0.8, "c2", original_filename="b.txt"),
    ]

    context = RAGPipeline._build_context(results)

    assert context.startswith("[1] (a.txt)")
    assert "[2] (b.txt)" in context


# ---------------------------------------------------------------------------
# Relevance cascade
# ---------------------------------------------------------------------------


def test_is_low_relevance_respects_config():
    """The low-relevance threshold comes from settings, not a literal."""
    from app.config import settings

    pipeline = make_pipeline()
    above = [make_result("t", settings.retrieval_low_relevance_threshold + 0.1, "c1")]
    below = [make_result("t", settings.retrieval_low_relevance_threshold - 0.1, "c1")]

    assert pipeline._is_low_relevance(above) is False
    assert pipeline._is_low_relevance(below) is True
    assert pipeline._is_low_relevance([]) is True


# ---------------------------------------------------------------------------
# No-results handling
# ---------------------------------------------------------------------------


def test_no_results_returns_fallback_message():
    """An empty retrieval with the loose prompt disabled yields a clear message."""
    from app.config import settings

    original = settings.loose_prompt_enabled
    settings.loose_prompt_enabled = False
    try:
        pipeline = make_pipeline(results=[])
        answer = pipeline.answer("unknown topic")

        assert "couldn't find" in answer.text.lower()
        assert answer.sources == []
    finally:
        settings.loose_prompt_enabled = original


# ---------------------------------------------------------------------------
# Hybrid retriever wiring
# ---------------------------------------------------------------------------


def test_search_uses_hybrid_retriever_when_configured():
    """The pipeline delegates to the hybrid retriever when one is injected."""
    retriever = Mock()
    retriever.search.return_value = [
        make_result("hit", 0.9, "c1", original_filename="a.txt")
    ]

    pipeline = make_pipeline(retriever=retriever)
    results = pipeline._search([0.1], question="a query")

    assert len(results) == 1
    retriever.search.assert_called_once()
    # BM25 needs the raw query text.
    assert retriever.search.call_args.kwargs["query"] == "a query"


def test_search_falls_back_to_vector_store_without_retriever():
    """Without a hybrid retriever the dense store is queried directly."""
    results = [make_result("hit", 0.9, "c1")]
    pipeline = make_pipeline(results=results)

    out = pipeline._search([0.1], question="a query")

    assert len(out) == 1
    pipeline._vector_store.search.assert_called_once()


def test_search_empty_result_returns_empty():
    """No matches yields an empty list, not an exception."""
    pipeline = make_pipeline(results=[])
    assert pipeline._search([0.1], question="q") == []
