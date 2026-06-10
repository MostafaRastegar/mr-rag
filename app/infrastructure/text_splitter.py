"""
LangChain Text Splitter Adapter.

Implements the TextSplitterPort interface using LangChain's
RecursiveCharacterTextSplitter for document chunking.
"""

import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.core.domain import Chunk, Document
from app.core.ports import TextSplitterPort

logger = logging.getLogger(__name__)


class LangChainTextSplitter(TextSplitterPort):
    """
    Splits documents into chunks using LangChain's RecursiveCharacterTextSplitter.

    This implementation uses LangChain under the hood for robust
    text splitting, but converts the results to our domain models.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size or settings.chunk_size,
            chunk_overlap=chunk_overlap or settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split a list of documents into smaller chunks.

        Args:
            documents: Documents to split.

        Returns:
            A list of Chunk objects.
        """
        if not documents:
            return []

        # Convert domain Documents to LangChain Documents for splitting
        lc_docs = [
            __import__("langchain_core.documents", fromlist=["Document"]).Document(
                page_content=doc.content, metadata=doc.metadata
            )
            for doc in documents
        ]

        # Split
        lc_chunks = self._splitter.split_documents(lc_docs)

        # Convert back to domain Chunks
        chunks = []
        for i, lc_chunk in enumerate(lc_chunks):
            chunks.append(
                Chunk(
                    id=f"chunk_{i}",
                    text=lc_chunk.page_content,
                    metadata={k: v for k, v in lc_chunk.metadata.items()},
                )
            )

        logger.info("Split %d documents into %d chunks", len(documents), len(chunks))
        return chunks
