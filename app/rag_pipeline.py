"""
RAG pipeline for question answering using LangChain chains.

This module orchestrates the retrieval-augmented generation workflow
using LangChain's RetrievalQA chain with a ChatPromptTemplate
for structured prompt management.
"""

import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.llm_service import LLMService
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Prompt template using LangChain's ChatPromptTemplate
RAG_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided context. "
    "Use only the information from the context to answer. "
    "If the context doesn't contain enough information, say so clearly."
)

RAG_USER_TEMPLATE = """Context:
{context}

Question: {question}

Answer based only on the context above:"""


class RAGPipeline:
    """Orchestrates retrieval and generation for question answering."""

    def __init__(
        self,
        llm_service: LLMService,
        vector_store: VectorStore,
    ) -> None:
        self.llm_service = llm_service
        self.vector_store = vector_store
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_SYSTEM_PROMPT),
                ("human", RAG_USER_TEMPLATE),
            ]
        )

    def answer(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using RAG.

        Args:
            question: The user's question.

        Returns:
            A dict containing the answer and source documents.
        """
        # Step 1: Retrieve relevant documents via vector store
        logger.info("Retrieving documents for: %s", question[:50])
        results = self.vector_store.search(
            query_text=question,
            top_k=settings.top_k,
        )

        if not results:
            logger.warning("No relevant documents found")
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
            }

        # Step 2: Build context and generate answer using chain
        context = self._build_context(results)
        logger.info("Generating answer with LLM...")
        answer = self._generate_answer(question, context)

        # Step 3: Extract source information
        sources = [
            {
                "content": r["document"][:200],
                "metadata": r["metadata"],
                "score": r.get("distance", 0),
            }
            for r in results
        ]

        return {
            "answer": answer,
            "sources": sources,
        }

    def _build_context(self, results: list[dict]) -> str:
        """Build a context string from retrieved documents."""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Document {i}] {result['document']}")
        return "\n\n".join(context_parts)

    def _generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the LLM with context."""
        messages = self._prompt.format_messages(
            context=context,
            question=question,
        )
        return str(self.llm_service.client.invoke(messages).content)
