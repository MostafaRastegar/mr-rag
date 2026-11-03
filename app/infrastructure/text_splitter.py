"""
LangChain Text Splitter Adapter.

Implements the TextSplitterPort interface using LangChain's
RecursiveCharacterTextSplitter for document chunking.
"""

import logging
import uuid
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.core.domain import Chunk, Document
from app.core.ports import TextSplitterPort
from app.infrastructure.text_normalizer import content_hash, normalize_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persian-aware separators.
#
# The default `["\n\n", "\n", " ", ""]` list has no sentence-level boundary,
# so Persian text is split mid-sentence and each chunk becomes a fragment.
# Adding the Persian/Arabic sentence and clause marks ("۔", ".", "،", "؛", "?",
# "!") lets the splitter cut at natural language boundaries first.
# ---------------------------------------------------------------------------

_PERSIAN_SEPARATORS = [
    "\n\n",
    "\n",
    "۔",  # Arabic full stop
    ".",
    "؟",  # Arabic question mark
    "?",
    "!",
    "؛",  # Arabic semicolon
    ";",
    "،",  # Arabic comma
    ",",
    " ",
    "",
]


class LangChainTextSplitter(TextSplitterPort):
    """
    Splits documents into chunks using LangChain's RecursiveCharacterTextSplitter.

    This implementation uses LangChain under the hood for robust
    text splitting, but converts the results to our domain models.

    Responsibilities beyond splitting:
      - Normalizes BOM / CRLF / excess whitespace before splitting, so stored
        chunks and the BM25 index see clean text.
      - Prepends the document's heading (when present) to each chunk so a
        fragment stays attributable to its section, which measurably improves
        retrieval for structured documents.
      - Stamps a content hash on every chunk to make duplicate detection
        possible on re-ingestion.
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
            separators=_PERSIAN_SEPARATORS,
        )

    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split a list of documents into smaller chunks.

        Args:
            documents: Documents to split.

        Returns:
            A list of Chunk objects with normalized text and content hashes.
        """
        if not documents:
            return []

        from langchain_core.documents import Document as LangChainDocument

        # Normalize text first so splitting, storage and BM25 all see the
        # same characters (no BOM, no CRLF, no blank-line runs).
        lc_docs = [
            LangChainDocument(
                page_content=normalize_text(doc.content),
                metadata=doc.metadata,
            )
            for doc in documents
        ]
        lc_docs = [d for d in lc_docs if d.page_content]

        if not lc_docs:
            logger.warning("All documents were empty after normalization")
            return []

        lc_chunks = self._splitter.split_documents(lc_docs)

        chunks: List[Chunk] = []
        seen_hashes: set[str] = set()

        for i, lc_chunk in enumerate(lc_chunks):
            text = normalize_text(lc_chunk.page_content)
            if not text:
                continue

            digest = content_hash(text)
            # Drop exact duplicates produced by overlap regions.
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)

            metadata = {k: v for k, v in lc_chunk.metadata.items()}
            metadata["content_hash"] = digest

            # Prefix the heading so a fragment keeps its section context.
            heading = metadata.get("header_1") or metadata.get("header_2")
            if heading:
                text = f"{heading}\n{text}"

            chunks.append(
                Chunk(
                    id=f"chunk_{uuid.uuid4().hex[:12]}_{i}",
                    text=text,
                    metadata=metadata,
                )
            )

        logger.info(
            "Split %d documents into %d chunks (chunk_size=%d, overlap=%d)",
            len(lc_docs),
            len(chunks),
            self._splitter._chunk_size,
            self._splitter._chunk_overlap,
        )
        return chunks

