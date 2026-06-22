"""
Abstract interfaces (Ports) for the RAG system.

These define the contracts that infrastructure adapters must implement,
following the Dependency Inversion Principle. High-level code depends
on these abstractions, not on concrete implementations.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List

from app.core.domain import Chunk, Document, DocumentInfo, Message, SearchResult


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

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """
        Delete chunks from the store by their IDs.

        Args:
            ids: List of chunk IDs to delete.
        """
        ...

    @abstractmethod
    def delete_by_metadata(self, key: str, value: str) -> int:
        """
        Delete chunks from the store by a metadata key-value pair.

        Args:
            key: The metadata field name.
            value: The metadata value to match.

        Returns:
            Number of deleted chunks.
        """
        ...

    def get_all_ids(self) -> list[str]:
        """
        Return all chunk IDs in the store.

        Default implementation returns an empty list.
        Override in adapters that support listing all IDs.
        """
        return []


class DocumentRepositoryPort(ABC):
    """Port for persisting and retrieving document metadata."""

    @abstractmethod
    def save(self, doc: DocumentInfo) -> None:
        """Save a document metadata record."""
        ...

    @abstractmethod
    def get(self, doc_id: str) -> DocumentInfo | None:
        """Get a document metadata record by ID."""
        ...

    @abstractmethod
    def list_all(self) -> list[DocumentInfo]:
        """List all document metadata records."""
        ...

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete a document metadata record by ID. Returns True if deleted."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the number of document metadata records."""
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
        Generate a response from the language model (blocking).

        Args:
            messages: Conversation messages.
            temperature: Controls randomness (0.0 to 1.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the language model.

        Yields tokens one by one as they arrive from the API.
        Uses SSE (Server-Sent Events) for real-time token delivery.

        Args:
            messages: Conversation messages.
            temperature: Controls randomness (0.0 to 1.0).
            max_tokens: Maximum tokens in the response.

        Yields:
            Tokens of the generated text as they arrive.
        """
        ...
        # Default implementation: yield nothing
        # Subclasses should override with actual streaming logic
        yield ""


class CachePort(ABC):
    """Port for caching LLM responses and embeddings."""

    @abstractmethod
    def lookup(self, prompt: str, llm_string: str) -> str | None:
        """
        Look up a cached response by prompt and LLM configuration.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.

        Returns:
            The cached text if found, otherwise None.
        """
        ...

    @abstractmethod
    def update(self, prompt: str, llm_string: str, value: str) -> None:
        """
        Store a response in the cache.

        Args:
            prompt: The serialized prompt / input text.
            llm_string: Serialized LLM configuration parameters.
            value: The response text to cache.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached entries."""
        ...

    # ------------------------------------------------------------------
    # Semantic (embedding-based) cache
    # ------------------------------------------------------------------

    def lookup_semantic(self, embedding: List[float], threshold: float) -> str | None:
        """
        Look up a cached response by semantic similarity of the query embedding.

        Default implementation returns None (no semantic caching).
        Override in adapters that support semantic matching.

        Args:
            embedding: The query embedding vector.
            threshold: Cosine similarity threshold (0.0-1.0).

        Returns:
            The cached answer text if a sufficiently similar query is found,
            otherwise None.
        """
        return None

    def update_semantic(self, embedding: List[float], value: str) -> None:
        """
        Store a response in the semantic cache keyed by its query embedding.

        Default implementation is a no-op.
        Override in adapters that support semantic matching.

        Args:
            embedding: The query embedding vector to use as the key.
            value: The answer text to cache.
        """
        ...

    def size(self) -> int:
        """
        Return the approximate number of entries in the cache.

        Default implementation returns 0.
        Override in adapters that can report their size.
        """
        return 0


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
