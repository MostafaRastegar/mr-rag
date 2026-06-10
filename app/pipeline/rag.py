"""
RAG Pipeline.

Orchestrates the retrieval-augmented generation workflow:
embed query → search vector store → build context → generate answer.
Depends only on abstract ports, not on concrete implementations.
Supports optional full Q&A caching via CachePort.
"""

import hashlib
import json
import logging
from typing import List, Optional

from app.config import settings
from app.core.domain import Answer, Message, SearchResult
from app.core.exceptions import RetrievalError
from app.core.ports import CachePort, EmbeddingPort, LLMPort, VectorStorePort

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Use only the information from the context to answer. "
    "If the context doesn't contain enough information, say so clearly."
)


class RAGPipeline:
    """
    Orchestrates retrieval and generation for question answering.

    Follows the Dependency Inversion Principle: depends on
    abstract ports injected at construction time.

    If a CachePort instance is provided, full question → answer
    results are cached. On repeated identical questions, the entire
    pipeline (embedding + search + LLM) is skipped and the cached
    answer is returned immediately for maximum speed.
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

    def answer(self, question: str) -> Answer:
        """
        Answer a question using RAG.

        Two-layer cache strategy:
        1. **Exact-match cache** (text hash) — for questions that are
           character-for-character identical to a previous question.
        2. **Semantic cache** (embedding cosine similarity) — for questions
           that are semantically similar but not textually identical.

        On cache hit at either layer, returns the cached Answer immediately
        without any search or LLM calls.

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

        # Step 2: Retrieve relevant documents
        try:
            results: List[SearchResult] = self._vector_store.search(
                query_embedding=query_embedding,
                top_k=settings.top_k,
            )
        except Exception as e:
            logger.error("Vector store search failed: %s", str(e))
            raise RetrievalError(f"Failed to search vector store: {e}") from e

        if not results:
            logger.warning("No relevant documents found for question")
            answer = Answer(
                text="I couldn't find any relevant information to answer your question.",
                sources=[],
            )
            # Cache the "no results" answer too
            if self._cache is not None:
                llm_string = json.dumps(
                    {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
                )
                self._cache.update(
                    question, llm_string, json.dumps({"text": answer.text})
                )
            return answer

        logger.info("Retrieved %d relevant chunks", len(results))

        # Step 3: Build context from retrieved documents
        context = self._build_context(results)

        # Step 4: Generate answer using LLM
        try:
            messages = [
                Message(role="system", content=SYSTEM_PROMPT),
                Message(
                    role="user",
                    content=f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer based only on the context above:",
                ),
            ]
            answer_text = self._llm.generate(messages)
        except Exception as e:
            logger.error("LLM generation failed: %s", str(e))
            raise RetrievalError(f"Failed to generate answer: {e}") from e

        answer = Answer(text=answer_text, sources=results)

        # Store full answer in cache for future identical questions
        if self._cache is not None:
            llm_string = json.dumps(
                {"pipeline": "rag", "top_k": settings.top_k}, sort_keys=True
            )
            self._cache.update(question, llm_string, json.dumps({"text": answer_text}))
            # Also store in semantic cache for similar future questions
            if settings.cache_semantic_enabled:
                self._cache.update_semantic(
                    query_embedding, json.dumps({"text": answer_text})
                )
            logger.info("RAG cache UPDATED")

        return answer

    def _build_context(self, results: List[SearchResult]) -> str:
        """Build a context string from retrieved search results."""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Document {i}] {result.chunk.text}")
        return "\n\n".join(context_parts)
