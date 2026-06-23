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
from app.core.ports import CachePort, EmbeddingPort, LLMPort, VectorStorePort

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LangChain Prompt Templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_STRICT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Use only the information from the context to answer. "
    "If the context doesn't contain enough information, say so clearly."
)

SYSTEM_PROMPT_LOOSE = (
    "You are a helpful assistant. Answer the user's question using the provided context "
    "as your primary source. If the context does not contain enough information to fully "
    "answer the question, you may supplement with your own knowledge — but clearly indicate "
    "which parts come from the provided context and which come from your general knowledge."
)

SYSTEM_PROMPT_GENERAL = "You are a helpful assistant. Answer the user's question based on your general knowledge."

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
            "Context:\n{context}\n\nConversation history:\n{history}\n\n"
            "Question: {question}\n\n"
            "Answer based only on the context above, using conversation history for reference:",
        ),
    ]
)

LOOSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_LOOSE),
        (
            "human",
            "Context:\n{context}\n\nConversation history:\n{history}\n\n"
            "Question: {question}\n\n"
            "Use the context as your primary source, but you may supplement "
            "with your own knowledge if it is insufficient. Clearly indicate "
            "which parts come from the context and which from your knowledge.",
        ),
    ]
)

GENERAL_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_GENERAL),
        ("human", "Conversation history:\n{history}\n\nQuestion: {question}"),
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
    ) -> None:
        self._embedding = embedding
        self._llm = llm
        self._vector_store = vector_store
        self._cache = cache

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
        except Exception as e:
            logger.error("LLM generation failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

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
        tokens progressively as they arrive from the LLM SSE stream.

        Args:
            question: The user's question.
            history: Optional list of {role, content} dicts from previous turns.

        Yields:
            Tokens of the generated answer as they become available.
        """
        logger.info("Processing streaming question: %s", question[:100])

        ctx = self._prepare_rag(question, history)
        if ctx.is_fallback_answer:
            yield ctx.fallback_answer_text
            return

        # Stream answer from LLM
        try:
            answer_parts: List[str] = []
            async for token in self._llm.generate_stream(ctx.messages):
                answer_parts.append(token)
                yield token
        except Exception as e:
            logger.error("LLM streaming failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        # Store full answer in cache
        full_answer = "".join(answer_parts)
        if full_answer:
            self._update_caches(question, ctx.query_embedding, full_answer)

    # ------------------------------------------------------------------
    # Shared RAG preparation (common to both answer and answer_stream)
    # ------------------------------------------------------------------

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
        # Stage 1 — Normal retrieval
        # ------------------------------------------------------------------
        use_cascade = settings.query_expansion_enabled or settings.loose_prompt_enabled
        results = self._search(
            query_embedding, allow_low_score_fallback=not use_cascade
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

        # Stage 3 — Loose prompt
        if settings.loose_prompt_enabled:
            logger.info("Loose prompt enabled — relaxing system prompt (Stage 3)")
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

        Returns True if the average score of all results is below 0.3,
        indicating the model couldn't find a good match and cascade is needed.
        """
        if not results:
            return True
        avg_score = sum(r.score for r in results) / len(results)
        logger.info("Average relevance score: %.4f (threshold: 0.30)", avg_score)
        return avg_score < 0.30

    def _search(
        self,
        query_embedding: List[float],
        allow_low_score_fallback: bool = True,
    ) -> List[SearchResult]:
        """
        Run a single search against the vector store and filter results.

        Args:
            query_embedding: The embedding vector to search with.
            allow_low_score_fallback: If True and all results are below min_score,
                keep the single best result (original behavior).
                If False, return empty list so the cascade (Stage 2/3) can proceed.

        Returns:
            A list of SearchResult objects that pass the min_score filter,
            or an empty list if nothing relevant was found.
        """
        try:
            results: List[SearchResult] = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=settings.top_k,
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

    @staticmethod
    def _build_context(results: List[SearchResult]) -> str:
        """Build a context string from retrieved search results."""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Document {i}] {result.chunk.text}")
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