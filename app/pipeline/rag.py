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
from typing import AsyncGenerator, List, cast

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

# System prompt strings (used directly since LLMPort expects Message objects)
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

# LangChain ChatPromptTemplates for structured prompt composition
STRICT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_STRICT),
        (
            "human",
            "Context:\n{context}\n\nQuestion: {question}\n\n"
            "Answer based only on the context above:",
        ),
    ]
)

LOOSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_LOOSE),
        (
            "human",
            "Context:\n{context}\n\nQuestion: {question}\n\n"
            "Use the context as your primary source, but you may supplement "
            "with your own knowledge if it is insufficient. Clearly indicate "
            "which parts come from the context and which from your knowledge.",
        ),
    ]
)

GENERAL_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_GENERAL),
        ("human", "Question: {question}"),
    ]
)

NO_CONTEXT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT_STRICT),
        (
            "human",
            "Question: {question}\n\n"
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
# LangChain's ChatPromptTemplate.format_messages() returns messages
# with .type = "human", "ai", etc. But the LLM API (OpenRouter/OpenAI)
# expects "user", "assistant", etc.
_ROLE_MAP: dict[str, str] = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
}


def _map_messages(
    formatted: list,
) -> list:
    """Convert LangChain formatted messages to domain Message objects with correct roles."""
    result: list = []
    for msg in formatted:
        msg_type: str = cast(str, msg.type) if msg.type is not None else "user"
        role: str = _ROLE_MAP.get(msg_type, msg_type)
        content: str = str(msg.content) if msg.content is not None else ""
        result.append(Message(role=role, content=content))
    return result


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

    def answer(self, question: str) -> Answer:
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

        Returns:
            An Answer object containing the generated text and sources.

        Raises:
            RetrievalError: If retrieval or generation fails.
        """
        logger.info("Processing question: %s", question[:100])

        # Layer 1: Try exact-match cache first (fastest — no embedding needed)
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
                    return Answer(text=data["text"], sources=[])
                except (json.JSONDecodeError, KeyError):
                    logger.warning("RAG cache entry malformed, re-running pipeline")

        # Step 1: Embed the question
        try:
            query_embedding = self._embedding.embed_query(question)
        except Exception as e:
            logger.error("Failed to embed query: %s", str(e))
            raise RetrievalError(f"Failed to embed query: {e}") from e

        # Layer 2: Try semantic cache (embedding similarity)
        if self._cache is not None and settings.cache_semantic_enabled:
            cached = self._cache.lookup_semantic(
                query_embedding, settings.cache_semantic_threshold
            )
            if cached is not None:
                logger.info("RAG cache (semantic) HIT — returning cached answer")
                try:
                    data = json.loads(cached)
                    return Answer(text=data["text"], sources=[])
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

        # If query expansion is enabled and cascade is needed → Stage 2
        if needs_expansion and settings.query_expansion_enabled:
            logger.info(
                "Stage 1 results low-relevance — trying query expansion (Stage 2)"
            )
            results = self._search_with_expansion(question)

        # If loose prompt is enabled → Stage 3 (regardless of Stage 2 outcome)
        if settings.loose_prompt_enabled:
            logger.info("Loose prompt enabled — relaxing system prompt (Stage 3)")
            use_loose_prompt = True

        if not results and not use_loose_prompt:
            logger.warning("No relevant documents found for question")
            answer = Answer(
                text="I couldn't find any relevant information to answer your question.",
                sources=[],
            )
            if self._cache is not None:
                llm_string = json.dumps(
                    {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
                )
                self._cache.update(
                    question, llm_string, json.dumps({"text": answer.text})
                )
            return answer

        # Build context from retrieved chunks (may be empty for Stage 3)
        context = self._build_context(results) if results else ""

        # Generate answer using LLM with the appropriate prompt template
        try:
            if context and not use_loose_prompt:
                formatted = STRICT_PROMPT.format_messages(
                    context=context, question=question
                )
            elif context and use_loose_prompt:
                formatted = LOOSE_PROMPT.format_messages(
                    context=context, question=question
                )
            elif not context and use_loose_prompt:
                formatted = GENERAL_PROMPT.format_messages(question=question)
            else:
                formatted = NO_CONTEXT_PROMPT.format_messages(question=question)

            messages = _map_messages(formatted)

            answer_text = self._llm.generate(messages)
        except Exception as e:
            logger.error("LLM generation failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        answer = Answer(text=answer_text, sources=results or [])

        # Store full answer in cache for future identical questions
        if self._cache is not None:
            llm_string = json.dumps(
                {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
            )
            self._cache.update(question, llm_string, json.dumps({"text": answer_text}))
            if settings.cache_semantic_enabled:
                self._cache.update_semantic(
                    query_embedding, json.dumps({"text": answer_text})
                )
            logger.info("RAG cache UPDATED")

        return answer

    # ------------------------------------------------------------------
    # Public API: streaming answer
    # ------------------------------------------------------------------

    async def answer_stream(self, question: str) -> AsyncGenerator[str, None]:
        """
        Answer a question using RAG with streaming response.

        Same three-stage cascading strategy as `answer()`, but yields
        tokens progressively as they arrive from the LLM SSE stream.

        Args:
            question: The user's question.

        Yields:
            Tokens of the generated answer as they become available.
        """
        logger.info("Processing streaming question: %s", question[:100])

        # Layer 1: Try exact-match cache first
        if self._cache is not None:
            llm_string = json.dumps(
                {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
            )
            cached = self._cache.lookup(question, llm_string)
            if cached is not None:
                logger.info("RAG streaming cache (exact) HIT")
                try:
                    data = json.loads(cached)
                    yield data["text"]
                    return
                except (json.JSONDecodeError, KeyError):
                    logger.warning("Cache entry malformed, re-running pipeline")

        # Step 1: Embed the question
        try:
            query_embedding = self._embedding.embed_query(question)
        except Exception as e:
            logger.error("Failed to embed query: %s", str(e))
            raise RetrievalError(f"Failed to embed query: {e}") from e

        # Layer 2: Try semantic cache
        if self._cache is not None and settings.cache_semantic_enabled:
            cached = self._cache.lookup_semantic(
                query_embedding, settings.cache_semantic_threshold
            )
            if cached is not None:
                logger.info("RAG streaming cache (semantic) HIT")
                try:
                    data = json.loads(cached)
                    yield data["text"]
                    return
                except (json.JSONDecodeError, KeyError):
                    logger.warning("Semantic cache entry malformed, re-running")

        # ------------------------------------------------------------------
        # Stage 1 — Normal retrieval
        # ------------------------------------------------------------------
        use_cascade = settings.query_expansion_enabled or settings.loose_prompt_enabled
        results = self._search(
            query_embedding, allow_low_score_fallback=not use_cascade
        )
        use_loose_prompt = False

        needs_expansion = not results or (
            use_cascade and results and self._is_low_relevance(results)
        )

        if needs_expansion and settings.query_expansion_enabled:
            logger.info(
                "Stage 1 results low-relevance — trying query expansion (Stage 2)"
            )
            results = self._search_with_expansion(question)

        if settings.loose_prompt_enabled:
            logger.info("Loose prompt enabled — relaxing system prompt (Stage 3)")
            use_loose_prompt = True

        if not results and not use_loose_prompt:
            logger.warning("No relevant documents found for question")
            yield "I couldn't find any relevant information to answer your question."
            return

        context = self._build_context(results) if results else ""

        # Stream answer from LLM using the appropriate prompt template
        try:
            if context and not use_loose_prompt:
                formatted = STRICT_PROMPT.format_messages(
                    context=context, question=question
                )
            elif context and use_loose_prompt:
                formatted = LOOSE_PROMPT.format_messages(
                    context=context, question=question
                )
            elif not context and use_loose_prompt:
                formatted = GENERAL_PROMPT.format_messages(question=question)
            else:
                formatted = NO_CONTEXT_PROMPT.format_messages(question=question)

            messages = _map_messages(formatted)

            answer_parts: List[str] = []
            async for token in self._llm.generate_stream(messages):
                answer_parts.append(token)
                yield token
        except Exception as e:
            logger.error("LLM streaming failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        # Store full answer in cache
        full_answer = "".join(answer_parts)
        if self._cache is not None and full_answer:
            llm_string = json.dumps(
                {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
            )
            self._cache.update(question, llm_string, json.dumps({"text": full_answer}))
            if settings.cache_semantic_enabled:
                self._cache.update_semantic(
                    query_embedding, json.dumps({"text": full_answer})
                )
            logger.info("RAG streaming cache UPDATED")

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
        self, query_embedding: List[float], allow_low_score_fallback: bool = True
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

        # Format the query expansion prompt using LangChain's template
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
