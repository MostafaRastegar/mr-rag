"""
Custom exception hierarchy for the RAG system.

Provides clear, typed exception classes that can be caught
and translated to appropriate HTTP responses in the API layer.
"""


class RAGException(Exception):
    """Base exception for all RAG-related errors."""


class DocumentLoadError(RAGException):
    """Raised when a document cannot be loaded from a source."""


class EmbeddingError(RAGException):
    """Raised when embedding generation fails."""


class VectorStoreError(RAGException):
    """Raised when a vector store operation fails."""


class LLMError(RAGException):
    """Raised when the LLM fails to generate a response."""


class IngestionError(RAGException):
    """Raised when the ingestion pipeline fails."""


class RetrievalError(RAGException):
    """Raised when the retrieval step of the RAG pipeline fails."""
