"""
Abstract interfaces (Ports) for the RAG system.

These define the contracts that infrastructure adapters must implement,
following the Dependency Inversion Principle. High-level code depends
on these abstractions, not on concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import List

from app.core.domain import Chunk, Document, Message, SearchResult


class EmbeddingPort(ABC):
    """Port for generating text embeddings."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string."""
        ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of text strings."""
        ...


class VectorStorePort(ABC):
    """Port for storing and retrieving vector embeddings."""

    @abstractmethod
    def add(self, chunks: List[Chunk], embeddings: List[List[float]]) -> int:
        """
        Add chunks with their embeddings to the store.

        Returns the number of chunks successfully added.
        """
        ...

    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int) -> List[SearchResult]:
        """
        Search for the most similar chunks given a query embedding.

        Returns results sorted by relevance (closest first).
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the number of documents in the store."""
        ...


class LLMPort(ABC):
    """Port for generating text using a language model."""

    @abstractmethod
    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a response from the language model.

        Args:
            messages: Conversation messages.
            temperature: Controls randomness (0.0 to 1.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text.
        """
        ...


class DocumentLoaderPort(ABC):
    """Port for loading documents from an external source."""

    @abstractmethod
    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a file path.

        Args:
            file_path: Path to the source file.

        Returns:
            A list of Document objects.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        ...


class TextSplitterPort(ABC):
    """Port for splitting documents into chunks."""

    @abstractmethod
    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split a list of documents into smaller chunks.

        Args:
            documents: Documents to split.

        Returns:
            A list of Chunk objects.
        """
        ...
