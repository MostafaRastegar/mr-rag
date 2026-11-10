"""
RAG Pipeline.

Orchestrates the retrieval-augmented generation workflow:
embed query → search vector store → build context → generate answer.
Depends only on abstract ports, not on concrete implementations.
Supports optional full Q&A caching via CachePort.

Three-stage cascading retrieval (controlled by settings flags):
  Stage 1 — Normal strict retrieval (current behavior)
  Stage 2 — Query Expansion (if no chunks found, re-phrase & retry)
  Stage 3 — Loose Prompt (if still no chunks, relax the system prompt)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, cast

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.core.domain import Answer, Message, SearchResult
from app.core.exceptions import RetrievalError
from app.core.ports import (
    CachePort,
    EmbeddingPort,
    LLMPort,
    RetrieverPort,
    RerankPort,
    VectorStorePort,
)
from app.infrastructure.science_normalizer import process as _science_process

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangChain Prompt Templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_STRICT = (
    "You are a precise assistant that answers STRICTLY from the provided "
    "context.\n\n"
    "Rules you must follow:\n"
    "1. Answer only from the context. Never invent facts, numbers, or names.\n"
    "2. Be specific and complete, never vague. Prefer concrete details over "
    "general statements. Do not pad the answer with filler.\n"
    "3. Answer in Persian (Farsi).\n"
    "4. Organize the answer as a bulleted list: one claim per bullet, each "
    "bullet starting with a short bolded title.\n"
    "5. Cite the source of each claim using the bracketed number of the "
    "context passage, e.g. [1] or [2], placed at the end of the bullet.\n"
    "6. When the question asks how to do something, give the steps in order.\n"
    "7. If the context only partially answers the question, answer the part "
    "it covers and explicitly state what is missing. Do not fill gaps with "
    "assumptions.\n"
    "8. If the context contains nothing relevant, say exactly: "
    "\"بر اساس منابع موجود، به این سوال جوابی یافت نشد.\"\n"
    "9. When the context or question contains math, chemistry, or biology "
    "symbols (formulas, equations, Greek letters, DNA/RNA, ATP, etc.), "
    "write them in LaTeX inline math using $...$ so the frontend can render "
    "them correctly (e.g. $H_2O$, $x^2$, $∫x dx$).\n"
    "10. When the context contains image descriptions (from PDF figures, "
    "diagrams, charts, or geometry shapes), treat them as first-class evidence. "
    "Describe what the image shows and cite it using its bracketed number.\\n"
    "11. End with a one-sentence conclusion summarizing the overall picture."
)

SYSTEM_PROMPT_LOOSE = (
    "You are a helpful assistant. Answer the user's question using the provided "
    "context as your primary source. If the context does not contain enough "
    "information to fully answer the question, you may supplement with your own "
    "knowledge — but clearly indicate which parts come from the provided "
    "context and which come from your general knowledge. Cite context passages "
    "using their bracketed number, e.g. [1]."
)

SYSTEM_PROMPT_GENERAL = (
    "You are a helpful assistant. Answer the user's question based on your "
    "general knowledge. Be specific and concrete; avoid vague generalities. "
    "State clearly that no project documents were available to ground the "
    "answer."
)

QUERY_EXPANSION_PROMPT_TEMPLATE = (
    "Rewrite the following question in {count} different ways. "
    "Use synonyms, rephrase the structure, and vary the wording to cover "
    "alternative phrasings of the same question. "
    "Output one variant per line, with no numbering, no bullet points, and no extra text."
)

STRICT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_STRICT),
        (
            "human",
            "Context passages:\n{context}\n\n"
            "Conversation history:\n{history}\n\n"
            "---\n"
            "Question: {question}\n\n"
            "Answer using ONLY the context passages above. Quote exact values "
            "verbatim, be specific rather than general, and cite passages as "
            "[1], [2], etc. Answer:",
        ),
    ]
)

LOOSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_LOOSE),
        (
            "human",
            "Context passages:\n{context}\n\n"
            "Conversation history:\n{history}\n\n"
            "---\n"
            "Question: {question}\n\n"
            "Prefer the context passages. Be specific inside the context's "
            "scope, cite them as [1], [2], etc., and clearly mark anything "
            "that comes from your own general knowledge. Answer:",
        ),
    ]
)

GENERAL_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_GENERAL),
        (
            "human",
            "Conversation history:\n{history}\n\n"
            "---\n"
            "Question: {question}\n\n"
            "No project context was retrieved. Be specific and state that the "
            "answer is not grounded in project documents. Answer:",
        ),
    ]
)

NO_CONTEXT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_STRICT),
        (
            "human",
            "Conversation history:\n{history}\n\n"
            "---\n"
            "Question: {question}\n\n"
            "No relevant context passages were retrieved. State clearly that "
            "the documents do not contain enough information to answer. Answer:",
        ),
    ]
)

NO_CONTEXT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_STRICT),
        (
            "human",
            "Conversation history:\n{history}\n\nQuestion: {question}\n\n"
            "No specific context was retrieved for this question.",
        ),
    ]
)

QUERY_EXPANSION_CHAT = ChatPromptTemplate.from_messages(
    [
        ("system", QUERY_EXPANSION_PROMPT_TEMPLATE),
        ("human", "{question}"),
    ]
)

_output_parser = StrOutputParser()

# ---------------------------------------------------------------------------
# Role mapper: LangChain message types → OpenAI API role names
# ---------------------------------------------------------------------------
_ROLE_MAP: dict[str, str] = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
}


def _map_messages(formatted: list) -> list:
    """Convert LangChain formatted messages to domain Message objects with correct roles."""
    result: list = []
    for msg in formatted:
        msg_type: str = cast(str, msg.type) if msg.type is not None else "user"
        role: str = _ROLE_MAP.get(msg_type, msg_type)
        content: str = str(msg.content) if msg.content is not None else ""
        result.append(Message(role=role, content=content))
    return result


def _source_label(metadata: dict | None) -> str | None:
    """Build a human-readable source label from chunk metadata (same as routes)."""
    if not metadata:
        return None
    name = metadata.get("original_filename") or metadata.get("source")
    if not name:
        return None
    label = str(name).split("/")[-1]
    if metadata.get("page") is not None:
        label = f"{label}, p.{metadata['page']}"
    elif metadata.get("section"):
        label = f"{label} — {metadata['section']}"
    return label


# ---------------------------------------------------------------------------
# Shared context for the RAG pipeline
# ---------------------------------------------------------------------------


@dataclass
class _RAGContext:
    """
    Carries all intermediate state produced by the shared RAG preparation phase.

    Both `answer()` and `answer_stream()` consume this context and only differ
    in how they run the final LLM generation (sync vs streaming).
    """

    messages: list = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)
    query_embedding: list[float] = field(default_factory=list)
    question: str = ""
    is_fallback_answer: bool = False
    fallback_answer_text: str = ""


class RAGPipeline:
    """
    Orchestrates retrieval and generation for question answering.

    Follows the Dependency Inversion Principle: depends on
    abstract ports injected at construction time.

    Supports a three-stage cascading strategy:
      1. Normal strict retrieval
      2. Query expansion (re-phrase and re-search)
      3. Loose prompt (relaxed system instruction)
    Each stage is gated by its respective setting flag.
    """

    def __init__(
        self,
        embedding: EmbeddingPort,
        llm: LLMPort,
        vector_store: VectorStorePort,
        cache: CachePort | None = None,
        reranker: RerankPort | None = None,
        retriever: RetrieverPort | None = None,
    ) -> None:
        """
        Args:
            embedding: Embedding provider.
            llm: Chat completion provider.
            vector_store: Dense retrieval backend.
            cache: Optional cache for answers and embeddings.
            reranker: Optional reranker for re-scoring candidates.
            retriever: Optional hybrid retriever exposing
                `search(query, query_embedding, top_k, fetch_k)`. When absent
                the pipeline falls back to the vector store directly.
        """
        self._embedding = embedding
        self._llm = llm
        self._vector_store = vector_store
        self._cache = cache
        self._reranker = reranker
        self._retriever = retriever

    # ------------------------------------------------------------------
    # Public API: blocking answer
    # ------------------------------------------------------------------

    def answer(self, question: str, history: List[Dict[str, str]] | None = None) -> Answer:
        """
        Answer a question using RAG with cascading retrieval strategy.

        Three-layer cache strategy:
        1. **Exact-match cache** (text hash) — for questions that are
           character-for-character identical to a previous question.
        2. **Semantic cache** (embedding cosine similarity) — for questions
           that are semantically similar but not textually identical.
        3. On cache miss: runs the full retrieval pipeline.

        Retrieval cascade:
        - Stage 1: Normal search + strict prompt
        - Stage 2 (if enabled): Query expansion when no chunks found
        - Stage 3 (if enabled): Loose prompt when still no chunks

        Args:
            question: The user's question.
            history: Optional list of {role, content} dicts from previous turns.

        Returns:
            An Answer object containing the generated text and sources.

        Raises:
            RetrievalError: If retrieval or generation fails.
        """
        logger.info("Processing question: %s", question[:100])

        ctx = self._prepare_rag(question, history)
        if ctx.is_fallback_answer:
            return Answer(text=ctx.fallback_answer_text, sources=[])

        # Generate answer via blocking LLM call
        try:
            answer_text = self._llm.generate(ctx.messages)
            if settings.science_detection_enabled:
                answer_text = _science_process(answer_text)
        except Exception as e:
            logger.error("LLM generation failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        # If the LLM found no relevant information, expose no sources.
        no_info_msg = "بر اساس منابع موجود، به این سوال جوابی یافت نشد."
        if answer_text.strip().startswith(no_info_msg):
            answer = Answer(text=answer_text, sources=[])
        else:
            answer = Answer(text=answer_text, sources=ctx.results)

        # Store full answer in cache
        self._update_caches(question, ctx.query_embedding, answer_text)

        return answer

    # ------------------------------------------------------------------
    # Public API: streaming answer
    # ------------------------------------------------------------------

    async def answer_stream(self, question: str, history: List[Dict[str, str]] | None = None) -> AsyncGenerator[str, None]:
        """
        Answer a question using RAG with streaming response.

        Same three-stage cascading strategy as `answer()`, but yields
        SSE-formatted events:
          - event: sources  (payload: list of source dicts, sent once)
          - event: token    (payload: generated text chunk)
          - event: done     (payload: empty, end of stream)

        Args:
            question: The user's question.
            history: Optional list of {role, content} dicts from previous turns.

        Yields:
            SSE-formatted strings consumed by the frontend.
        """
        logger.info("Processing streaming question: %s", question[:100])

        ctx = self._prepare_rag(question, history)
        if ctx.is_fallback_answer:
            payload = json.dumps(
                {"text": ctx.fallback_answer_text, "sources": []},
                ensure_ascii=False,
            )
            yield f"event: sources\ndata: []\n\n"
            yield f"event: done\ndata: {payload}\n\n"
            return

        no_info_msg = "بر اساس منابع موجود، به این سوال جوابی یافت نشد."

        # Stream answer from LLM token by token
        answer_parts: List[str] = []
        try:
            async for token in self._llm.generate_stream(ctx.messages):
                answer_parts.append(token)
                yield f"event: token\ndata: {json.dumps(token, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("LLM streaming failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        full_answer = "".join(answer_parts)
        if settings.science_detection_enabled:
            full_answer = _science_process(full_answer)

        # If the LLM found no relevant information, expose no sources.
        if full_answer.strip().startswith(no_info_msg):
            yield f"event: sources\ndata: []\n\n"
        else:
            sources_payload = [
                {
                    "content": s.chunk.text[:200],
                    "metadata": s.chunk.metadata,
                    "score": s.score,
                    "source_name": _source_label(s.chunk.metadata),
                    "chunk_id": s.chunk.id or None,
                }
                for s in ctx.results
            ]
            yield f"event: sources\ndata: {json.dumps(sources_payload, ensure_ascii=False)}\n\n"

        # Store full answer in cache
        if full_answer:
            self._update_caches(question, ctx.query_embedding, full_answer)

        yield "event: done\ndata: \n\n"


    def _prepare_rag(self, question: str, history: List[Dict[str, str]] | None = None) -> _RAGContext:
        """
        Execute the shared portion of the RAG pipeline:
          cache checks → embedding → retrieval → cascade → prompt building.

        This method is used by both `answer()` and `answer_stream()` to
        avoid code duplication. After calling this, each method only needs
        to run the LLM generation (sync or streaming) and cache the result.

        Args:
            question: The user's question.
            history: Optional list of {role, content} dicts from previous turns.

        Returns:
            A _RAGContext containing the built messages, retrieval results,
            query embedding, and any fallback answer if no retrieval is possible.
        """
        ctx = _RAGContext(question=question)

        # ------------------------------------------------------------------
        # Layer 1: Try exact-match cache first (fastest — no embedding needed)
        # ------------------------------------------------------------------
        if self._cache is not None:
            llm_string = json.dumps(
                {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
            )
            cached = self._cache.lookup(question, llm_string)
            if cached is not None:
                logger.info(
                    "RAG cache (exact) HIT — returning cached answer immediately"
                )
                try:
                    data = json.loads(cached)
                    ctx.is_fallback_answer = True
                    ctx.fallback_answer_text = data["text"]
                    return ctx
                except (json.JSONDecodeError, KeyError):
                    logger.warning("RAG cache entry malformed, re-running pipeline")

        # ------------------------------------------------------------------
        # Step 1: Embed the question
        # ------------------------------------------------------------------
        try:
            query_embedding = self._embedding.embed_query(question)
        except Exception as e:
            logger.error("Failed to embed query: %s", str(e))
            raise RetrievalError(f"Failed to embed query: {e}") from e

        ctx.query_embedding = query_embedding

        # ------------------------------------------------------------------
        # Layer 2: Try semantic cache (embedding similarity)
        # ------------------------------------------------------------------
        if self._cache is not None and settings.cache_semantic_enabled:
            cached = self._cache.lookup_semantic(
                query_embedding, settings.cache_semantic_threshold
            )
            if cached is not None:
                logger.info("RAG cache (semantic) HIT — returning cached answer")
                try:
                    data = json.loads(cached)
                    ctx.is_fallback_answer = True
                    ctx.fallback_answer_text = data["text"]
                    return ctx
                except (json.JSONDecodeError, KeyError):
                    logger.warning(
                        "Semantic cache entry malformed, re-running pipeline"
                    )

        # ------------------------------------------------------------------
        # Stage 1 — Normal retrieval (hybrid: dense + BM25 when enabled)
        # ------------------------------------------------------------------
        use_cascade = settings.query_expansion_enabled or settings.loose_prompt_enabled
        results = self._search(
            query_embedding,
            allow_low_score_fallback=not use_cascade,
            question=question,
        )
        use_loose_prompt = False

        # Cascade trigger: empty results OR low-relevance results
        needs_expansion = not results or (
            use_cascade and results and self._is_low_relevance(results)
        )

        # Stage 2 — Query expansion
        if needs_expansion and settings.query_expansion_enabled:
            logger.info(
                "Stage 1 results low-relevance — trying query expansion (Stage 2)"
            )
            results = self._search_with_expansion(question)

        # Stage 2b — Multi-query retrieval (LangChain MultiQueryRetriever)
        # Used when the question is multi-part / long and Stage 1 was weak.
        if (
            needs_expansion
            and settings.multi_query_enabled
            and results
            and self._is_low_relevance(results)
        ):
            logger.info("Stage 1 weakly relevant — trying multi-query retrieval (Stage 2b)")
            mq_results = self._search_multi_query(question)
            if mq_results:
                results = mq_results

        # ------------------------------------------------------------------
        # Stage 2c — LLM reranking of the candidate pool
        # The reranker narrows a large candidate set down to the most
        # relevant chunks, which is what stops the model from answering with
        # generic summaries built from loosely-related context.
        # ------------------------------------------------------------------
        if results and settings.rerank_enabled:
            results = self._rerank(question, results)

        # ------------------------------------------------------------------
        # Stage 3 — Loose prompt
        # IMPORTANT: only relax the system prompt when retrieval genuinely
        # failed OR produced weakly-relevant context. Previously this fired
        # unconditionally whenever the flag was on, which made the model lean
        # on its own general knowledge even when good context was available —
        # the main cause of vague, generic answers.
        # ------------------------------------------------------------------
        if settings.loose_prompt_enabled and self._should_use_loose_prompt(results):
            logger.info(
                "Weak or empty context — relaxing system prompt (Stage 3)"
            )
            use_loose_prompt = True

        # Handle no results
        if not results and not use_loose_prompt:
            logger.warning("No relevant documents found for question")
            fallback_text = (
                "I couldn't find any relevant information to answer your question."
            )
            ctx.is_fallback_answer = True
            ctx.fallback_answer_text = fallback_text
            # Cache the "no results" answer too
            if self._cache is not None:
                llm_string = json.dumps(
                    {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
                )
                self._cache.update(
                    question, llm_string, json.dumps({"text": fallback_text})
                )
            return ctx

        ctx.results = results

        # Build context from retrieved chunks (may be empty for Stage 3)
        context = self._build_context(results) if results else ""
        if settings.science_detection_enabled:
            context = _science_process(context)

        # Build history string for the prompt templates
        history_str = self._format_history(history or [])

        # Select the appropriate prompt template and build messages
        try:
            if context and not use_loose_prompt:
                formatted = STRICT_PROMPT.format_messages(
                    context=context, history=history_str, question=question
                )
            elif context and use_loose_prompt:
                formatted = LOOSE_PROMPT.format_messages(
                    context=context, history=history_str, question=question
                )
            elif not context and use_loose_prompt:
                formatted = GENERAL_PROMPT.format_messages(
                    history=history_str, question=question
                )
            else:
                formatted = NO_CONTEXT_PROMPT.format_messages(
                    history=history_str, question=question
                )

            ctx.messages = _map_messages(formatted)
        except Exception as e:
            logger.error("Failed to build prompt: %s", str(e))
            raise RetrievalError(f"Failed to build prompt: {e}") from e

        return ctx

    # ------------------------------------------------------------------
    # Cache update helper
    # ------------------------------------------------------------------

    def _update_caches(
        self, question: str, query_embedding: list[float], answer_text: str
    ) -> None:
        """Store the generated answer in both exact-match and semantic caches."""
        if self._cache is None:
            return

        llm_string = json.dumps(
            {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
        )
        self._cache.update(question, llm_string, json.dumps({"text": answer_text}))

        if settings.cache_semantic_enabled:
            self._cache.update_semantic(
                query_embedding, json.dumps({"text": answer_text})
            )

        logger.info("RAG cache UPDATED")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_low_relevance(results: List[SearchResult]) -> bool:
        """
        Check if the retrieved results have low relevance overall.

        Returns True if the average score of all results is below
        `settings.retrieval_low_relevance_threshold`, indicating the model
        couldn't find a good match and the cascade stages should run.

        The threshold is configurable rather than hardcoded because the right
        value depends on the embedding model's similarity distribution.
        """
        if not results:
            return True
        avg_score = sum(r.score for r in results) / len(results)
        threshold = settings.retrieval_low_relevance_threshold
        logger.info(
            "Average relevance score: %.4f (threshold: %.2f)", avg_score, threshold
        )
        return avg_score < threshold

    def _should_use_loose_prompt(self, results: List[SearchResult]) -> bool:
        """
        Decide whether the system prompt should be relaxed (Stage 3).

        The loose prompt allows the model to fall back on its own general
        knowledge, which is only appropriate when retrieval produced nothing
        usable. If good context exists we must keep the strict prompt so the
        answer stays grounded in the documents.

        Returns:
            True only when there are no results, or the results are weak
            enough that grounding the answer would be misleading.
        """
        if not results:
            logger.info("No context available — loose prompt is appropriate")
            return True

        avg_score = sum(r.score for r in results) / len(results)
        threshold = settings.retrieval_low_relevance_threshold
        if avg_score < threshold:
            logger.info(
                "Context relevance %.4f below %.2f — loose prompt is appropriate",
                avg_score,
                threshold,
            )
            return True

        logger.info(
            "Context relevance %.4f is sufficient — keeping strict grounded prompt",
            avg_score,
        )
        return False

    def _search(
        self,
        query_embedding: List[float],
        allow_low_score_fallback: bool = True,
        question: str = "",
    ) -> List[SearchResult]:
        """
        Run a single search and filter results.

        Uses the hybrid retriever (BM25 + dense) when one is configured,
        otherwise the dense vector store directly. A wide candidate pool is
        fetched so the reranker has enough material to work with.

        Args:
            query_embedding: The embedding vector to search with.
            allow_low_score_fallback: If True and all results are below min_score,
                keep the single best result (original behavior).
                If False, return empty list so the cascade (Stage 2/3) can proceed.
            question: The raw question text, required for BM25 keyword matching.

        Returns:
            A list of SearchResult objects that pass the min_score filter,
            or an empty list if nothing relevant was found.
        """
        pool = max(settings.fetch_k, settings.top_k)
        try:
            if self._retriever is not None and settings.hybrid_search_enabled and question:
                results: List[SearchResult] = self._retriever.search(
                    query=question,
                    query_embedding=query_embedding,
                    top_k=pool,
                    fetch_k=pool,
                )
            else:
                results = self._vector_store.search(
                    query_embedding=query_embedding,
                    top_k=pool,
                )
        except Exception as e:
            logger.error("Vector store search failed: %s", str(e))
            raise RetrievalError(f"Failed to search vector store: {e}") from e

        if not results:
            return []

        min_score = settings.retrieval_min_score
        if min_score > 0:
            filtered = [r for r in results if r.score >= min_score]
            if filtered:
                logger.info(
                    "Filtered %d/%d low-scoring chunks (min_score=%.2f)",
                    len(results) - len(filtered),
                    len(results),
                    min_score,
                )
                results = filtered
            elif allow_low_score_fallback:
                logger.warning(
                    "All chunks below min_score=%.2f, keeping the best one", min_score
                )
                results = results[:1]
            else:
                logger.warning(
                    "All chunks below min_score=%.2f — returning empty for cascade",
                    min_score,
                )
                return []

        logger.info("Retrieved %d relevant chunks", len(results))
        return results

    def _expand_query(self, question: str) -> List[str]:
        """
        Use the LLM to generate alternative phrasings of the user's question.

        Uses LangChain's ChatPromptTemplate for structured prompt formatting.

        Returns:
            A list of alternative question strings (including the original).
        """
        count = settings.query_expansion_count
        if count < 1:
            return [question]

        formatted = QUERY_EXPANSION_CHAT.format_messages(
            count=str(count), question=question
        )
        messages = _map_messages(formatted)

        try:
            raw = self._llm.generate(messages, temperature=0.7, max_tokens=512)
        except Exception as e:
            logger.warning(
                "Query expansion failed: %s — using original question only", str(e)
            )
            return [question]

        variants = [line.strip() for line in raw.splitlines() if line.strip()]
        all_queries = [question] + variants[:count]
        logger.info(
            "Query expansion generated %d variant(s): %s",
            len(all_queries) - 1,
            all_queries,
        )
        return all_queries

    def _search_with_expansion(self, question: str) -> List[SearchResult]:
        """
        Expand the query into multiple phrasings, embed each, and merge results.

        Returns:
            A merged list of SearchResult objects (deduplicated by chunk ID),
            or an empty list if nothing was found.
        """
        queries = self._expand_query(question)
        seen_ids: set[str] = set()
        merged: List[SearchResult] = []

        for q in queries:
            try:
                emb = self._embedding.embed_query(q)
            except Exception as e:
                logger.warning(
                    "Failed to embed expanded query '%s': %s", q[:50], str(e)
                )
                continue

            try:
                batch: List[SearchResult] = self._vector_store.search(
                    query_embedding=emb,
                    top_k=settings.top_k,
                )
            except Exception as e:
                logger.warning(
                    "Search failed for expanded query '%s': %s", q[:50], str(e)
                )
                continue

            for result in batch:
                if result.chunk.id and result.chunk.id not in seen_ids:
                    seen_ids.add(result.chunk.id)
                    merged.append(result)

            if len(merged) >= settings.top_k:
                logger.info(
                    "Collected %d unique chunks from expansion, stopping early",
                    len(merged),
                )
                break

        if not merged:
            logger.warning("Query expansion returned no results either")
            return []

        merged.sort(key=lambda r: r.score, reverse=True)

        min_score = settings.retrieval_min_score
        if min_score > 0:
            filtered = [r for r in merged if r.score >= min_score]
            if filtered:
                merged = filtered
        merged = merged[: settings.top_k]

        logger.info("Merged %d unique chunks from query expansion", len(merged))
        return merged

    def _rerank(
        self, question: str, results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Re-score candidates with the reranker and keep the best `rerank_top_n`.

        Reranking is skipped when no reranker is configured, when results are
        already within the target size, or when the reranker itself is
        disabled. Failures fall back to the retrieval order so answering never
        breaks because of reranking.

        Returns:
            The reranked subset, or the input unchanged when reranking is
            unavailable.
        """
        target = settings.rerank_top_n or settings.top_k

        if self._reranker is None:
            return results[:target] if target else results

        if len(results) <= 1:
            return results[:target] if target else results

        try:
            reranked = self._reranker.rerank(question, results, top_k=target)
        except Exception as e:
            logger.warning(
                "Rerank failed (%s) — keeping retrieval order", str(e)
            )
            return results[:target]

        if not reranked:
            logger.warning("Reranker returned nothing — keeping retrieval order")
            return results[:target]

        logger.info(
            "Rerank: %d candidates → %d chunks (top score %.3f)",
            len(results),
            len(reranked),
            reranked[0].score,
        )
        return reranked

    def _search_multi_query(self, question: str) -> List[SearchResult]:
        """
        Retrieve over multiple phrasings of the question and fuse with RRF.

        Complements Stage 2 query expansion: this path merges ranked lists via
        Reciprocal Rank Fusion instead of taking the single best-scoring list,
        which surfaces chunks that only one phrasing happens to match.

        Returns:
            A merged, deduplicated list, or an empty list when nothing was
            found or the expansion produced no usable variants.
        """
        try:
            queries = self._expand_query(question)
        except Exception as e:
            logger.warning("Multi-query expansion failed: %s", str(e))
            return []

        if len(queries) <= 1:
            return []

        rrf_k = 60.0
        fused: dict[str, dict] = {}

        for query in queries:
            try:
                embedding = self._embedding.embed_query(query)
                results = self._search(embedding, question=query)
            except Exception as e:
                logger.warning(
                    "Multi-query search failed for '%s': %s", query[:50], str(e)
                )
                continue

            for rank, result in enumerate(results):
                key = result.chunk.id or result.chunk.text[:200]
                entry = fused.setdefault(key, {"result": result, "score": 0.0})
                entry["score"] += 1.0 / (rrf_k + rank + 1)
                if result.score > entry["result"].score:
                    entry["result"] = result

        if not fused:
            return []

        ordered = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
        top_score = ordered[0]["score"]
        merged = [
            SearchResult(
                chunk=entry["result"].chunk,
                score=round(entry["score"] / top_score, 4) if top_score else 0.0,
            )
            for entry in ordered
        ]

        logger.info(
            "Multi-query retrieval: %d phrasings → %d unique chunks",
            len(queries),
            len(merged),
        )
        return merged

    @staticmethod
    def _build_context(results: List[SearchResult]) -> str:
        """
        Build a context string from retrieved search results.

        Each chunk is labelled with a numbered citation and a human-readable
        source so the model can reference specific documents and the caller
        can map an assertion back to its origin. The temporary-path metadata
        (`source` pointing at `/tmp/...`) is intentionally not used, because it
        is meaningless to both the model and the user.
        """
        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result.chunk.metadata or {}
            origin = (
                metadata.get("original_filename")
                or metadata.get("source")
                or "unknown"
            )
            origin = str(origin).split("/")[-1]
            if metadata.get("page") is not None:
                origin = f"{origin}, p.{metadata['page']}"
            elif metadata.get("section"):
                origin = f"{origin} — {metadata['section']}"

            context_parts.append(f"[{i}] ({origin}) {result.chunk.text}")
        return "\n\n".join(context_parts)

    @staticmethod
    def _format_history(history: List[Dict[str, str]]) -> str:
        """Format conversation history into a string for inclusion in prompts."""
        if not history:
            return ""
        parts = []
        for msg in history:
            role_label = "User" if msg.get("role") == "user" else "Assistant"
            parts.append(f"{role_label}: {msg.get('content', '')}")
        return "\n".join(parts)