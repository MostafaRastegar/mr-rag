"""
LLM-based Reranker Adapter.

Implements the RerankPort interface using the configured chat LLM for
listwise relevance scoring.

Why LLM-based: OpenRouter exposes no dedicated rerank endpoint, and local
CrossEncoder models are unavailable in this deployment (no torch /
sentence-transformers). The chat LLM is therefore the only reranker available.

Uses LangChain's `BaseDocumentCompressor` so the adapter stays interoperable
with LangChain's compression pipeline while still satisfying our Port.
"""

import json
import logging
import re
from typing import List, Sequence

from langchain_core.documents import Document as LangChainDocument
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.core.domain import Chunk, Message, SearchResult
from app.core.ports import LLMPort, RerankPort

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangChain prompt template for listwise relevance scoring
# ---------------------------------------------------------------------------

RERANK_SYSTEM_PROMPT = (
    "You are a search result reranker. You score how well each candidate "
    "passage answers the user's question.\n\n"
    "Scoring rules:\n"
    "- 9-10: passage directly and completely answers the question\n"
    "- 6-8: passage contains most of the needed information\n"
    "- 3-5: passage is related but only partially useful\n"
    "- 0-2: passage is unrelated or only shares keywords\n\n"
    "Judge by whether the passage actually answers the question, not by "
    "surface keyword overlap. A passage that merely repeats the question's "
    "words but contains no answer must score low.\n\n"
    'Respond with ONLY a JSON object of the form {{"scores": [n1, n2, ...]}} '
    "containing exactly one integer score per passage, in the order given."
)

RERANK_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", RERANK_SYSTEM_PROMPT),
        (
            "human",
            "Question: {question}\n\n"
            "Candidate passages:\n{passages}\n\n"
            'Return JSON: {{"scores": [...]}}',
        ),
    ]
)

_ROLE_MAP: dict[str, str] = {"human": "user", "ai": "assistant", "system": "system"}


def _map_messages(formatted: list) -> List[Message]:
    """Convert LangChain formatted messages into domain Message objects."""
    mapped: List[Message] = []
    for msg in formatted:
        msg_type = getattr(msg, "type", None) or "user"
        role = _ROLE_MAP.get(str(msg_type), str(msg_type))
        content = str(msg.content) if msg.content is not None else ""
        mapped.append(Message(role=role, content=content))
    return mapped


class LLMReranker(BaseDocumentCompressor, RerankPort):
    """
    Reranks candidates by asking the chat LLM to score each one.

    The adapter degrades gracefully: any failure (API error, unparseable
    output, score count mismatch) falls back to the original retrieval order,
    so answering never breaks because of reranking.

    Implements both `RerankPort` (our hexagonal contract) and LangChain's
    `BaseDocumentCompressor` (for interoperability).
    """

    def __init__(
        self,
        llm: LLMPort,
        max_tokens: int | None = None,
    ) -> None:
        """
        Args:
            llm: The chat LLM used for scoring.
            max_tokens: Token budget for the scoring call.
        """
        # BaseDocumentCompressor is a pydantic model; no extra fields needed.
        super().__init__()
        self._llm = llm
        self._max_tokens = max_tokens or settings.rerank_max_tokens

    # ------------------------------------------------------------------
    # RerankPort
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        Score candidates with the LLM and return the best `top_k` first.

        Falls back to the incoming order (truncated to `top_k`) when the
        scoring call fails or returns unusable output.
        """
        if not results:
            return []

        if len(results) == 1:
            return results[:top_k]

        scores = self._score_passages(query, results)
        if scores is None:
            logger.warning(
                "Rerank unavailable — falling back to retrieval order for %d candidates",
                len(results),
            )
            return results[:top_k]

        scored: List[tuple[float, int, SearchResult]] = []
        for index, result in enumerate(results):
            raw = scores[index] if index < len(scores) else 0.0
            # Normalise the 0-10 score onto 0.0-1.0.
            normalized = max(0.0, min(1.0, raw / 10.0))
            scored.append((normalized, index, result))

        min_score = settings.rerank_min_score / 10.0
        above = [item for item in scored if item[0] >= min_score]

        # If the reranker dislikes everything, keep the best few rather than
        # returning nothing — the caller already handled the empty case.
        selected = above if above else sorted(scored, reverse=True)[:top_k]

        # Best score first; original retrieval order breaks ties for stability.
        selected.sort(key=lambda item: (-item[0], item[1]))

        reranked = [
            SearchResult(chunk=result.chunk, score=round(normalized, 4))
            for normalized, _, result in selected[:top_k]
        ]

        logger.info(
            "Reranked %d candidates → kept %d (min_score=%.2f)",
            len(results),
            len(reranked),
            settings.rerank_min_score,
        )
        return reranked

    # ------------------------------------------------------------------
    # LangChain BaseDocumentCompressor
    # ------------------------------------------------------------------

    def compress_documents(
        self,
        documents: Sequence[LangChainDocument],
        query: str,
        callbacks=None,
    ) -> Sequence[LangChainDocument]:
        """
        LangChain-compatible compression entry point.

        Converts LangChain Documents to SearchResults, reranks them, and
        returns the surviving Documents in ranked order.
        """
        results = [
            SearchResult(
                chunk=Chunk(
                    text=doc.page_content,
                    metadata=dict(doc.metadata),
                    id=str(doc.metadata.get("id", "")),
                ),
                score=0.0,
            )
            for doc in documents
        ]

        reranked = self.rerank(query, results, top_k=len(results))
        return [
            LangChainDocument(
                page_content=item.chunk.text, metadata=item.chunk.metadata
            )
            for item in reranked
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_passages(
        self, query: str, results: List[SearchResult]
    ) -> List[float] | None:
        """
        Ask the LLM to score every candidate passage.

        Returns:
            A list of 0-10 scores aligned with `results`, or None when the
            call fails or the response cannot be parsed.
        """
        passages = "\n\n".join(
            f"[{i + 1}] {r.chunk.text[:1200]}" for i, r in enumerate(results)
        )

        try:
            formatted = RERANK_PROMPT.format_messages(
                question=query, passages=passages
            )
            messages = _map_messages(formatted)
            raw = self._llm.generate(
                messages, temperature=0.0, max_tokens=self._max_tokens
            )
        except Exception as e:
            logger.warning("Rerank LLM call failed: %s", str(e))
            return None

        scores = self._parse_scores(raw, expected=len(results))
        if scores is None:
            logger.warning("Could not parse rerank scores from LLM output")
        return scores

    @staticmethod
    def _parse_scores(raw: str, expected: int) -> List[float] | None:
        """
        Extract the score list from the LLM response.

        Accepts a strict JSON object and falls back to scraping the first
        bracketed list of numbers, because free-tier models occasionally wrap
        JSON in prose or code fences.
        """
        text = (raw or "").strip()
        if not text:
            return None

        # Strip markdown code fences if present.
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

        parsed: object | None = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\[([^\[\]]*)\]", text)
            if match:
                try:
                    parsed = json.loads(f"[{match.group(1)}]")
                except json.JSONDecodeError:
                    parsed = None

        values: list | None = None
        if isinstance(parsed, dict):
            candidate = parsed.get("scores")
            if isinstance(candidate, list):
                values = candidate
        elif isinstance(parsed, list):
            values = parsed

        if not values:
            return None

        scores: List[float] = []
        for value in values:
            try:
                scores.append(float(value))
            except (TypeError, ValueError):
                scores.append(0.0)

        if len(scores) != expected:
            logger.warning(
                "Rerank score count mismatch: got %d, expected %d",
                len(scores),
                expected,
            )
            return None

        return scores
