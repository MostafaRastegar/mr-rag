"""
Text splitter for document chunking.

This module provides a configured text splitter that chunks
documents into smaller pieces for embedding and retrieval.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def create_text_splitter() -> RecursiveCharacterTextSplitter:
    """
    Create a configured text splitter.

    Returns:
        A RecursiveCharacterTextSplitter with chunk_size=1024
        and chunk_overlap=200.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
