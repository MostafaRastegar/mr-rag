"""
Domain models for the RAG system.

Pure data objects with no external dependencies.
Define the core business entities used throughout the application.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """A raw document loaded from an external source (e.g., JSON file)."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A chunk of text produced by splitting a Document."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class SearchResult:
    """A single result from a vector store search."""

    chunk: Chunk
    score: float = 0.0


@dataclass
class Answer:
    """The final answer produced by the RAG pipeline."""

    text: str
    sources: list[SearchResult] = field(default_factory=list)


@dataclass
class Message:
    """A single message in a chat conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class DocumentInfo:
    """
    Metadata about an ingested document.

    Tracks which files have been ingested, when, and how many chunks they produced.
    """

    id: str
    filename: str
    source_path: str
    file_type: str  # "json", "md", "txt"
    chunk_count: int
    ingested_at: float  # Unix timestamp


@dataclass
class ConversationMessage:
    """A single message within a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float  # Unix timestamp


@dataclass
class Conversation:
    """A chat conversation with history."""

    id: str
    title: str
    messages: list[ConversationMessage]
    created_at: float  # Unix timestamp
    updated_at: float  # Unix timestamp
