"""
RAG pipeline for question answering.

This module orchestrates the retrieval-augmented generation workflow:
embed the question, retrieve relevant documents from ChromaDB,
build a prompt with context, and generate an answer using OpenRouter LLM.
"""

import logging
from typing import List, Dict, Any

from app.config import settings
from app.embedding_service import EmbeddingService
from app.llm_service import LLMService
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Orchestrates retrieval and generation for question answering."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.vector_store = vector_store

    def answer(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using RAG.

        Args:
            question: The user's question.

        Returns:
            A dict containing the answer and source documents.
        """
        # Step 1: Embed the question
        logger.info("Embedding question: %s", question[:50])
        query_embedding = self.embedding_service.embed(question)

        # Step 2: Retrieve relevant documents
        logger.info("Retrieving relevant documents...")
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=settings.top_k,
        )

        if not results:
            logger.warning("No relevant documents found")
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
            }

        # Step 3: Build context from retrieved documents
        context = self._build_context(results)

        # Step 4: Generate answer using LLM
        logger.info("Generating answer with LLM...")
        answer = self._generate_answer(question, context)

        # Step 5: Extract source information
        sources = [
            {
                "content": r["document"][:200],
                "metadata": r["metadata"],
                "score": round(1.0 - r.get("distance", 0), 4),
            }
            for r in results
        ]

        return {
            "answer": answer,
            "sources": sources,
        }

    def _build_context(self, results: List[dict]) -> str:
        """Build a context string from retrieved documents."""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Document {i}] {result['document']}")
        return "\n\n".join(context_parts)

    def _generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the LLM with context."""
        system_prompt = (
            "You are a helpful assistant that answers questions based on the provided context. "
            "Use only the information from the context to answer. "
            "If the context doesn't contain enough information, say so clearly."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}\n\n"
                    f"Answer based only on the context above:"
                ),
            },
        ]

        return self.llm_service.generate(messages)