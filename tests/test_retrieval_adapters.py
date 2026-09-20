"""
Tests for the hybrid retriever and LLM reranker adapters.

The vector store is a mock so these tests stay fast and offline, per the
project's port-mocking convention.
"""

from unittest.mock import Mock

from app.core.domain import Chunk, Message, SearchResult
from app.infrastructure.hybrid_retriever import HybridRetriever, persian_preprocess
from app.infrastructure.llm_reranker import LLMReranker
from app.infrastructure.text_normalizer import content_hash, normalize_text


# ---------------------------------------------------------------------------
# Persian tokenization
# ---------------------------------------------------------------------------


def test_persian_preprocess_splits_zwnj():
    """Zero-width non-joiner must act as a token separator."""
    tokens = persian_preprocess("نیم‌فاصله")
    assert "نیم" in tokens
    assert "فاصله" in tokens


def test_persian_preprocess_unifies_arabic_variants():
    """Arabic yeh/kaf spellings must map onto the Persian forms."""
    tokens = persian_preprocess("فيوز كليد")
    assert "فیوز" in tokens
    assert "کلید" in tokens


def test_persian_preprocess_lowercases_technical_terms():
    """Latin technical terms are lowercased for case-insensitive matching."""
    assert "tl431" in persian_preprocess("TL431 regulator")


def test_persian_preprocess_handles_empty():
    """Empty and whitespace-only input yields no tokens."""
    assert persian_preprocess("") == []
    assert persian_preprocess("   ") == []


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------


def test_normalize_text_strips_bom_and_crlf():
    """BOM and CRLF must be removed so chunk text is clean."""
    result = normalize_text("\ufeffhello\r\n\r\n\r\nworld")
    assert "\ufeff" not in result
    assert "\r" not in result
    assert result == "hello\n\nworld"


def test_normalize_text_collapses_inline_whitespace():
    """Runs of spaces collapse to one."""
    assert normalize_text("a    b") == "a b"


def test_normalize_text_preserves_zwnj():
    """ZWNJ is semantically meaningful in Persian and must be preserved."""
    assert "\u200c" in normalize_text("نیم‌فاصله")


def test_content_hash_is_stable_across_line_endings():
    """The same content with CRLF and LF must hash identically."""
    assert content_hash("a\r\nb") == content_hash("a\nb")


# ---------------------------------------------------------------------------
# Hybrid retriever
# ---------------------------------------------------------------------------


def _chunk(text: str, chunk_id: str) -> Chunk:
    return Chunk(text=text, metadata={}, id=chunk_id)


def make_hybrid_store(chunks: list[Chunk], dense_results: list[SearchResult]):
    """Build a mocked vector store for hybrid retriever tests."""
    store = Mock()
    store.count.return_value = len(chunks)
    store.get_all_chunks.return_value = chunks
    store.search.return_value = dense_results
    return store


def test_hybrid_search_dedups_across_retrievers():
    """A chunk found by both BM25 and dense appears only once."""
    chunks = [
        _chunk("فیوز ورودی حفاظت اتصال کوتاه", "c1"),
        _chunk("وریستور VDR اضافه ولتاژ", "c2"),
        _chunk("طرز تهیه قورمه سبزی", "c3"),
    ]
    dense = [
        SearchResult(chunk=chunks[0], score=0.9),
        SearchResult(chunk=chunks[1], score=0.8),
    ]
    store = make_hybrid_store(chunks, dense)

    hybrid = HybridRetriever(store, bm25_weight=0.4)
    results = hybrid.search("فیوز حفاظت", [0.1], top_k=5)

    ids = [r.chunk.id for r in results]
    assert len(ids) == len(set(ids)), "results must be deduplicated"


def test_hybrid_search_returns_top_k():
    """No more than top_k results are returned."""
    chunks = [_chunk(f"متن شماره {i}", f"c{i}") for i in range(10)]
    dense = [SearchResult(chunk=c, score=0.9 - i * 0.05) for i, c in enumerate(chunks)]
    store = make_hybrid_store(chunks, dense)

    hybrid = HybridRetriever(store, bm25_weight=0.5)
    results = hybrid.search("متن", [0.1], top_k=3)

    assert len(results) == 3


def test_hybrid_falls_back_to_dense_when_bm25_unavailable():
    """If the BM25 index cannot be built, dense results are still returned."""
    store = Mock()
    store.count.side_effect = RuntimeError("store unavailable")
    store.search.return_value = [
        SearchResult(chunk=_chunk("dense hit", "c1"), score=0.7)
    ]

    hybrid = HybridRetriever(store, bm25_weight=0.4)
    results = hybrid.search("query", [0.1], top_k=5)

    assert len(results) == 1
    assert results[0].chunk.id == "c1"


def test_hybrid_handles_empty_store():
    """An empty store yields no results instead of raising."""
    store = Mock()
    store.count.return_value = 0
    store.get_all_chunks.return_value = []
    store.search.return_value = []

    hybrid = HybridRetriever(store, bm25_weight=0.4)

    assert hybrid.search("query", [0.1], top_k=5) == []


# ---------------------------------------------------------------------------
# LLM reranker
# ---------------------------------------------------------------------------


def _results(count: int) -> list[SearchResult]:
    return [SearchResult(chunk=_chunk(f"passage {i}", f"c{i}"), score=0.5) for i in range(count)]


def test_rerank_orders_by_llm_scores():
    """Higher-scored passages come first and scores are normalized to 0-1."""
    llm = Mock()
    # 2/10 = 0.2 is below rerank_min_score, so c0 is dropped.
    llm.generate.return_value = '{"scores": [2, 9, 5]}'

    reranker = LLMReranker(llm=llm)
    out = reranker.rerank("q", _results(3), top_k=3)

    assert [r.chunk.id for r in out] == ["c1", "c2"]
    assert out[0].score == 0.9
    assert out[1].score == 0.5


def test_rerank_keeps_all_when_all_scores_high():
    """When every passage scores above the floor, all are kept and ordered."""
    llm = Mock()
    llm.generate.return_value = '{"scores": [4, 9, 6]}'

    reranker = LLMReranker(llm=llm)
    out = reranker.rerank("q", _results(3), top_k=3)

    assert [r.chunk.id for r in out] == ["c1", "c2", "c0"]


def test_rerank_drops_low_scores():
    """Passages below rerank_min_score are filtered out."""
    from app.config import settings

    llm = Mock()
    # 1/10 = 0.1, below the 0.3 default threshold.
    llm.generate.return_value = '{"scores": [10, 1]}'

    reranker = LLMReranker(llm=llm)
    out = reranker.rerank("q", _results(2), top_k=2)

    assert len(out) == 1
    assert out[0].chunk.id == "c0"
    assert settings.rerank_min_score > 0


def test_rerank_falls_back_on_llm_failure():
    """An LLM error returns the original order, never raises."""
    llm = Mock()
    llm.generate.side_effect = RuntimeError("api down")

    results = _results(3)
    reranker = LLMReranker(llm=llm)
    out = reranker.rerank("q", results, top_k=2)

    assert [r.chunk.id for r in out] == ["c0", "c1"]


def test_rerank_falls_back_on_unparseable_output():
    """Garbage LLM output returns the original order instead of failing."""
    llm = Mock()
    llm.generate.return_value = "I cannot score these."

    results = _results(3)
    reranker = LLMReranker(llm=llm)
    out = reranker.rerank("q", results, top_k=2)

    assert [r.chunk.id for r in out] == ["c0", "c1"]


def test_rerank_single_result_short_circuits():
    """A single candidate is returned without calling the LLM."""
    llm = Mock()
    reranker = LLMReranker(llm=llm)

    out = reranker.rerank("q", _results(1), top_k=5)

    assert len(out) == 1
    llm.generate.assert_not_called()


def test_rerank_empty_input():
    """No candidates means no results and no LLM call."""
    llm = Mock()
    reranker = LLMReranker(llm=llm)

    assert reranker.rerank("q", [], top_k=5) == []
    llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Score parsing
# ---------------------------------------------------------------------------


def test_parse_scores_accepts_json_object():
    assert LLMReranker._parse_scores('{"scores": [1, 2, 3]}', 3) == [1.0, 2.0, 3.0]


def test_parse_scores_accepts_bare_list():
    assert LLMReranker._parse_scores("[4, 5]", 2) == [4.0, 5.0]


def test_parse_scores_accepts_code_fences():
    raw = '```json\n{"scores": [8, 2]}\n```'
    assert LLMReranker._parse_scores(raw, 2) == [8.0, 2.0]


def test_parse_scores_accepts_prose_wrapper():
    """Free-tier models often wrap JSON in extra prose."""
    assert LLMReranker._parse_scores("Here you go: [7, 1]", 2) == [7.0, 1.0]


def test_parse_scores_rejects_count_mismatch():
    """A mismatched count is unusable and must be rejected."""
    assert LLMReranker._parse_scores('{"scores": [1, 2]}', 3) is None


def test_parse_scores_rejects_empty_and_garbage():
    assert LLMReranker._parse_scores("", 1) is None
    assert LLMReranker._parse_scores("no numbers here", 1) is None


def test_reranker_satisfies_rerank_port():
    """The adapter must satisfy the RerankPort contract."""
    from app.core.ports import RerankPort

    assert issubclass(LLMReranker, RerankPort)


def test_reranker_maps_langchain_messages_to_domain_roles():
    """Formatted LangChain messages must map onto OpenAI role names."""
    llm = Mock()
    llm.generate.return_value = '{"scores": [5, 5]}'

    reranker = LLMReranker(llm=llm)
    reranker.rerank("q", _results(2), top_k=2)

    messages = llm.generate.call_args.args[0]
    assert isinstance(messages[0], Message)
    assert messages[0].role == "system"
    assert messages[1].role == "user"
