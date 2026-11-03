"""
Hybrid Search Adapter.

Combines BM25 keyword retrieval with dense vector retrieval using LangChain's
`BM25Retriever` and `EnsembleRetriever`.

Why hybrid: dense-only retrieval with a small embedding model misses exact
technical terms — part numbers, model names, error codes (e.g. "TL431",
"LM358", "2SC"). BM25 catches those literal matches, while the dense side
handles paraphrase and synonym questions. Fusing both materially improves
which chunks reach the LLM.

Wraps LangChain retrievers behind our Port contract and converts results back
to domain models.
"""

import logging
import re
from typing import List

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document as LangChainDocument

from app.config import settings
from app.core.domain import Chunk, SearchResult
from app.core.ports import VectorStorePort

logger = logging.getLogger(__name__)


def persian_preprocess(text: str) -> List[str]:
    """
    Tokenize text for BM25 with Persian-aware normalization.

    Handles details that break naive whitespace splitting on Persian text:
      - Zero-width non-joiner (U+200C, "نیم‌فاصله") is treated as a separator,
        so "نیم‌فاصله" also matches "نیم فاصله".
      - Arabic/Persian letter variants are unified (ي→ی, ك→ک) so spelling
        differences do not fragment term matching.
      - Punctuation is stripped and tokens shorter than 2 chars dropped.

    Args:
        text: Raw text to tokenize.

    Returns:
        A list of normalized tokens.
    """
    if not text:
        return []

    normalized = (
        text.replace("\u200c", " ")
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ۀ", "ه")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .lower()
    )
    tokens = re.split(r"[^\w\u0600-\u06FF]+", normalized)
    return [t for t in tokens if len(t) > 1]


class HybridRetriever:
    """
    Fuses BM25 keyword search with dense vector search.

    A fresh BM25 index is built over the current vector-store contents and
    cached in memory; it is rebuilt automatically when the chunk count
    changes (i.e. after ingestion or deletion), so the adapter stays correct
    without explicit invalidation calls.

    Takes the VectorStorePort as its dense backend. The query embedding is
    supplied by the caller per query, so the dense side does not need to call
    the embedding API itself.
    """

    def __init__(
        self,
        vector_store: VectorStorePort,
        bm25_weight: float | None = None,
    ) -> None:
        """
        Args:
            vector_store: Dense retrieval backend.
            bm25_weight: Share of the ensemble given to BM25 (0.0-1.0). The
                remainder goes to the dense retriever.
        """
        self._vector_store = vector_store
        self._bm25_weight = (
            bm25_weight if bm25_weight is not None else settings.hybrid_bm25_weight
        )
        self._bm25: BM25Retriever | None = None
        self._indexed_count: int = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int,
        fetch_k: int | None = None,
    ) -> List[SearchResult]:
        """
        Run a hybrid search and return fused results.

        Args:
            query: The raw query text (used by BM25).
            query_embedding: The query embedding (used by the dense side).
            top_k: Number of results to return.
            fetch_k: Candidate pool size per retriever. Defaults to
                `settings.fetch_k`, always at least `top_k`.

        Returns:
            Fused results ordered by ensemble score, best first. Falls back to
            dense-only results if the BM25 index cannot be built.
        """
        pool = max(fetch_k or settings.fetch_k, top_k)

        bm25_docs = self._bm25_search(query, pool)
        dense_docs = self._dense_search(query_embedding, pool)

        if not bm25_docs:
            logger.info("Hybrid: BM25 returned nothing, using dense results only")
            return dense_docs[:top_k]

        if not dense_docs:
            logger.info("Hybrid: dense returned nothing, using BM25 results only")
            return bm25_docs[:top_k]

        fused = self._fuse(bm25_docs, dense_docs, pool)
        logger.info(
            "Hybrid retrieval: %d BM25 + %d dense → %d fused (bm25_weight=%.2f)",
            len(bm25_docs),
            len(dense_docs),
            len(fused),
            self._bm25_weight,
        )
        return fused[:top_k]

    # ------------------------------------------------------------------
    # Retrievers
    # ------------------------------------------------------------------

    def _ensure_bm25(self) -> bool:
        """
        Build (or rebuild) the BM25 index from the vector store.

        Rebuilds only when the stored chunk count changed, keeping the index
        fresh after ingestion/deletion without a full rebuild per query.

        Returns:
            True when the index is ready, False when unavailable.
        """
        try:
            current_count = self._vector_store.count()
        except Exception as e:
            logger.warning("Hybrid: cannot count vector store: %s", str(e))
            return False

        if self._bm25 is not None and current_count == self._indexed_count:
            return True

        try:
            chunks: List[Chunk] = self._vector_store.get_all_chunks()
        except Exception as e:
            logger.warning("Hybrid: cannot load chunks for BM25 index: %s", str(e))
            return False

        if not chunks:
            logger.info("Hybrid: vector store is empty, BM25 index not built")
            self._bm25 = None
            self._indexed_count = -1
            return False

        documents = [
            LangChainDocument(
                page_content=chunk.text,
                metadata={**chunk.metadata, "id": chunk.id},
            )
            for chunk in chunks
        ]

        try:
            retriever = BM25Retriever.from_documents(
                documents, preprocess_func=persian_preprocess
            )
        except Exception as e:
            logger.warning("Hybrid: failed to build BM25 index: %s", str(e))
            return False

        retriever.k = max(settings.fetch_k, settings.top_k)
        self._bm25 = retriever
        self._indexed_count = current_count
        logger.info(
            "Hybrid: built BM25 index over %d chunks (count=%d)",
            len(documents),
            current_count,
        )
        return True

    def _bm25_search(self, query: str, pool: int) -> List[SearchResult]:
        """Run BM25 keyword search, returning empty on failure."""
        if not self._ensure_bm25() or self._bm25 is None:
            return []

        try:
            self._bm25.k = pool
            docs = self._bm25.invoke(query)
        except Exception as e:
            logger.warning("Hybrid: BM25 search failed: %s", str(e))
            return []

        return self._to_search_results(docs, pool)

    def _dense_search(
        self, query_embedding: List[float], pool: int
    ) -> List[SearchResult]:
        """Run dense vector search, returning empty on failure."""
        try:
            return self._vector_store.search(query_embedding, pool)
        except Exception as e:
            logger.warning("Hybrid: dense search failed: %s", str(e))
            return []

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    def _fuse(
        self,
        bm25_results: List[SearchResult],
        dense_results: List[SearchResult],
        pool: int,
    ) -> List[SearchResult]:
        """
        Fuse two ranked lists with weighted Reciprocal Rank Fusion.

        RRF is used instead of score averaging because BM25 scores and cosine
        similarities live on incomparable scales; rank positions are always
        comparable. Weighting balances the two signals without needing to
        normalize raw scores.

        Returns:
            Fused results ordered best first, deduplicated by chunk id (or
            leading text when no id is present).
        """
        rrf_k = 60.0
        fused: dict[str, dict] = {}

        def add(items: List[SearchResult], weight: float) -> None:
            for rank, item in enumerate(items):
                key = self._dedup_key(item)
                entry = fused.setdefault(key, {"result": item, "score": 0.0})
                entry["score"] += weight / (rrf_k + rank + 1)
                # Keep the higher-scoring representation for reporting.
                if item.score > entry["result"].score:
                    entry["result"] = item

        add(bm25_results, self._bm25_weight)
        add(dense_results, 1.0 - self._bm25_weight)

        ordered = sorted(fused.values(), key=lambda e: e["score"], reverse=True)

        # Normalise the fused score onto 0.0-1.0 so downstream min_score
        # filtering stays meaningful.
        top_score = ordered[0]["score"] if ordered else 0.0
        results: List[SearchResult] = []
        for entry in ordered[:pool]:
            normalized = entry["score"] / top_score if top_score > 0 else 0.0
            results.append(
                SearchResult(chunk=entry["result"].chunk, score=round(normalized, 4))
            )
        return results

    @staticmethod
    def _dedup_key(result: SearchResult) -> str:
        """Build a stable dedup key: prefer chunk id, fall back to text."""
        if result.chunk.id:
            return result.chunk.id
        return result.chunk.text[:200]

    @staticmethod
    def _to_search_results(
        docs: List[LangChainDocument], pool: int
    ) -> List[SearchResult]:
        """
        Convert LangChain Documents to domain SearchResults.

        BM25 exposes no similarity score, so rank position is mapped onto a
        decaying 0.0-1.0 value. These are used for reporting and as a
        tie-breaker — the ensemble rank is what orders the final results.
        """
        results: List[SearchResult] = []
        total = max(len(docs), 1)
        for rank, doc in enumerate(docs[:pool]):
            metadata = dict(doc.metadata)
            chunk_id = str(metadata.pop("id", ""))
            results.append(
                SearchResult(
                    chunk=Chunk(
                        text=doc.page_content,
                        metadata=metadata,
                        id=chunk_id,
                    ),
                    score=round(1.0 - (rank / total), 4),
                )
            )
        return results
