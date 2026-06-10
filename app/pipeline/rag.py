"""
RAG Pipeline.

Orchestrates the retrieval-augmented generation workflow:
embed query → search vector store → build context → generate answer.
Depends only on abstract ports, not on concrete implementations.
"""

import logging
from typing import List

from app.config import settings
from app.core.domain import Answer, Message, SearchResult
from app.core.exceptions import RetrievalError
from app.core.ports import EmbeddingPort, LLMPort, VectorStorePort

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
    """

    def __init__(
        self,
        embedding: EmbeddingPort,
        llm: LLMPort,
        vector_store: VectorStorePort,
    ) -> None:
        self._embedding = embedding
        self._llm = llm
        self._vector_store = vector_store

    def answer(self, question: str) -> Answer:
        """
        Answer a question using RAG.

        Args:
            question: The user's question.

        Returns:
            An Answer object containing the generated text and sources.

        Raises:
            RetrievalError: If retrieval or generation fails.
        """
        logger.info("Processing question: %s", question[:100])

        # Step 1: Embed the question
        try:
            query_embedding = self._embedding.embed_query(question)
        except Exception as e:
            logger.error("Failed to embed query: %s", str(e))
            raise RetrievalError(f"Failed to embed query: {e}") from e

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
            return Answer(
                text="I couldn't find any relevant information to answer your question.",
                sources=[],
            )

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

        return Answer(text=answer_text, sources=results)

    def _build_context(self, results: List[SearchResult]) -> str:
        """Build a context string from retrieved search results."""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Document {i}] {result.chunk.text}")
        return "\n\n".join(context_parts)
