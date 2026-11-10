"""
Jev relevance reranker adapter.

Implements ``RerankPort`` using TypeSafe Jev (via OpenRouter's System One
API) to re-score retrieved chunks without generating text.

The adapter wraps ``jev-relevance``'s provider factory and scoring
strategies, converting between the project's ``SearchResult`` domain type
and LangChain ``Document`` objects that Jev expects.

Fail-open: any scoring failure returns the input order truncated to
``top_k``, so the RAG pipeline never loses context because Jev is down.
"""

from __future__ import annotations

import logging
from typing import List, Sequence

from langchain_core.documents import Document as LangChainDocument
from langchain_typesafe import TypeSafeClassifier

from app.config import settings
from app.core.domain import Chunk, SearchResult
from app.core.ports import RerankPort
from jev_relevance.config import JevRelevanceConfig, ProviderConfig
from jev_relevance.provider import build_classifier
from jev_relevance.strategies import build_scoring_strategy

logger = logging.getLogger(__name__)


class JevReranker(RerankPort):
    """
    Re-scores retrieved candidates with TypeSafe Jev relevance judgments.

    Jev is a discriminative model: given a (query, passage) state it returns
    a probability (noul mode) or a 0..3 grade (score mode) that the passage
    answers the query. It does *not* generate text, which makes it cheap and
    fast as a pre-reranker before the LLM.

    Parameters
    ----------
    enabled:
        When False, ``rerank`` returns the input order unchanged.
    model:
        Jev model id on the provider (e.g. ``"typesafe/jev-1.13"``).
    provider:
        ``"openrouter"`` or ``"typesafe"``.
    base_url:
        Provider API root URL.
    api_key:
        Bearer token for the provider.
    question_mode:
        ``"noul"`` → yes/no probability in [0, 1].
        ``"score"``  → 0..3 rubric grade.
    scoring_mode:
        ``"per_chunk"`` → one Jev call per query-passage pair (most accurate).
        ``"batched"``   → one request for all chunks (faster, max 32).
    threshold:
        Noul-mode cutoff (0..1). Chunks below are dropped.
    score_threshold:
        Score-mode cutoff (0..3). Chunks below are dropped.
    max_concurrency:
        Max in-flight Jev calls in per-chunk mode.
    timeout_s:
        HTTP timeout for Jev API calls.
    fail_open:
        On scoring failure, return unfiltered candidates instead of raising.
    """

    def __init__(
        self,
        enabled: bool = False,
        model: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        question_mode: str | None = None,
        scoring_mode: str | None = None,
        threshold: float | None = None,
        score_threshold: float | None = None,
        max_concurrency: int | None = None,
        timeout_s: float | None = None,
        fail_open: bool | None = None,
    ) -> None:
        self.enabled = enabled
        self._model = model or settings.jev_model
        self._provider = provider or settings.jev_provider
        self._base_url = base_url or settings.jev_base_url
        self._api_key = api_key or settings.openrouter_api_key
        self._question_mode = question_mode or settings.jev_question_mode
        self._scoring_mode = scoring_mode or settings.jev_scoring_mode
        self._threshold = threshold if threshold is not None else settings.jev_threshold
        self._score_threshold = (
            score_threshold if score_threshold is not None else settings.jev_score_threshold
        )
        self._max_concurrency = max_concurrency or settings.jev_max_concurrency
        self._timeout_s = timeout_s or settings.jev_timeout_s
        self._fail_open = fail_open if fail_open is not None else settings.jev_fail_open

        self._classifier: TypeSafeClassifier | None = None
        self._strategy = None
        self._built = False

    def _ensure_built(self) -> None:
        """Build the Jev classifier + strategy on first use."""
        if self._built:
            return
        try:
            provider_config = ProviderConfig(
                name=self._provider,  # type: ignore[arg-type]
                model=self._model,
                api_key=self._api_key,
                base_url=self._base_url,
                timeout_s=self._timeout_s,
            )
            self._classifier = build_classifier(provider_config)

            config = JevRelevanceConfig(
                question_mode=self._question_mode,  # type: ignore[arg-type]
                scoring_mode=self._scoring_mode,  # type: ignore[arg-type]
                threshold=self._threshold,
                score_threshold=self._score_threshold,
                max_concurrency=self._max_concurrency,
                fail_open=self._fail_open,
            )
            self._strategy = build_scoring_strategy(self._classifier, config)
        except Exception as e:
            logger.warning("Jev reranker failed to initialize: %s", str(e))
            self._classifier = None
            self._strategy = None
        self._built = True

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        Score candidates with Jev and return the best ``top_k`` first.

        When disabled or on failure, returns the input order truncated to
        ``top_k`` (fail-open).
        """
        if not results:
            return []

        if not self.enabled:
            return results[:top_k]

        self._ensure_built()
        if self._strategy is None:
            logger.warning("Jev reranker unavailable — falling back to retrieval order")
            return results[:top_k]

        if len(results) == 1:
            return results[:top_k]

        documents = [
            LangChainDocument(page_content=r.chunk.text, metadata=dict(r.chunk.metadata or {}))
            for r in results
        ]

        try:
            scores = self._strategy.score(query, documents)
        except Exception as e:
            logger.warning("Jev rerank scoring failed: %s", str(e))
            if self._fail_open:
                return results[:top_k]
            raise

        scored: List[tuple[float, int, SearchResult]] = []
        for index, (result, doc_score) in enumerate(zip(results, scores)):
            relevance = doc_score.relevance
            if self._question_mode == "score":
                normalized = max(0.0, min(1.0, relevance / 3.0))
            else:
                normalized = max(0.0, min(1.0, relevance))

            cutoff = (
                self._score_threshold / 3.0 if self._question_mode == "score" else self._threshold
            )
            if normalized < cutoff:
                continue

            scored.append((normalized, index, result))

        if not scored:
            scored = [
                (r.score if hasattr(r, "score") else 0.0, i, r)
                for i, r in enumerate(results)
            ][:top_k]

        scored.sort(key=lambda item: (-item[0], item[1]))

        reranked = [
            SearchResult(chunk=result.chunk, score=round(normalized, 4))
            for normalized, _, result in scored[:top_k]
        ]

        logger.info(
            "Jev reranked %d candidates → kept %d (mode=%s, threshold=%.2f)",
            len(results),
            len(reranked),
            self._question_mode,
            cutoff,
        )
        return reranked


__all__ = ["JevReranker"]
