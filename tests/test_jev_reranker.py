"""
Unit tests for JevReranker.

Jev itself calls the OpenRouter System One API, so these tests mock the
underlying classifier/strategy and verify the adapter contract:
- disabled passthrough
- reranking + threshold filtering
- fail-open on scoring failure
- RerankPort interface satisfaction
"""

from typing import List

import pytest

from app.core.domain import Chunk, SearchResult
from app.core.ports import RerankPort
from app.infrastructure.jev_reranker import JevReranker


class _FakeStrategy:
    """Stand-in for jev_relevance.strategies.ScoringStrategy."""

    def __init__(self, scores: List[float] | None = None, raise_on_score: bool = False):
        self._scores = scores or [0.9, 0.4, 0.7]
        self._raise = raise_on_score
        self.called = 0

    def score(self, query: str, documents: list):
        self.called += 1
        if self._raise:
            raise RuntimeError("Jev API down")
        # Return one DocumentScore-like object per document.
        from types import SimpleNamespace
        return [
            SimpleNamespace(document=documents[i], relevance=self._scores[i], confidence=None)
            for i in range(len(documents))
        ]


@pytest.fixture
def chunks() -> List[SearchResult]:
    return [
        SearchResult(chunk=Chunk(text="chunk A", metadata={}), score=0.1),
        SearchResult(chunk=Chunk(text="chunk B", metadata={}), score=0.2),
        SearchResult(chunk=Chunk(text="chunk C", metadata={}), score=0.3),
    ]


def test_jev_disabled_returns_input_order(chunks):
    reranker = JevReranker(enabled=False)
    out = reranker.rerank("q", chunks, top_k=10)
    assert [r.chunk.text for r in out] == ["chunk A", "chunk B", "chunk C"]


def test_jev_reranks_with_mocked_strategy(chunks, monkeypatch):
    reranker = JevReranker(enabled=True, threshold=0.0)
    fake = _FakeStrategy(scores=[0.9, 0.4, 0.7])
    monkeypatch.setattr(reranker, "_ensure_built", lambda: None)
    monkeypatch.setattr(reranker, "_strategy", fake)
    out = reranker.rerank("q", chunks, top_k=10)
    assert [r.chunk.text for r in out] == ["chunk A", "chunk C", "chunk B"]
    assert fake.called == 1


def test_jev_threshold_filters(chunks, monkeypatch):
    reranker = JevReranker(enabled=True, threshold=0.6)
    fake = _FakeStrategy(scores=[0.9, 0.4, 0.7])
    monkeypatch.setattr(reranker, "_ensure_built", lambda: None)
    monkeypatch.setattr(reranker, "_strategy", fake)
    out = reranker.rerank("q", chunks, top_k=10)
    # Only chunk A (0.9) and chunk C (0.7) clear 0.6
    assert [r.chunk.text for r in out] == ["chunk A", "chunk C"]


def test_jev_fail_open_on_scoring_error(chunks, monkeypatch):
    reranker = JevReranker(enabled=True, fail_open=True, threshold=0.0)
    fake = _FakeStrategy(scores=[0.9, 0.4, 0.7], raise_on_score=True)
    monkeypatch.setattr(reranker, "_ensure_built", lambda: None)
    monkeypatch.setattr(reranker, "_strategy", fake)
    out = reranker.rerank("q", chunks, top_k=10)
    assert [r.chunk.text for r in out] == ["chunk A", "chunk B", "chunk C"]


def test_jev_satisfies_rerank_port():
    from app.core.ports import RerankPort
    assert issubclass(JevReranker, RerankPort)


def test_jev_empty_results():
    reranker = JevReranker(enabled=True)
    assert reranker.rerank("q", [], top_k=5) == []


def test_jev_single_result_passthrough(chunks):
    reranker = JevReranker(enabled=True)
    single = [chunks[0]]
    out = reranker.rerank("q", single, top_k=5)
    assert out == single