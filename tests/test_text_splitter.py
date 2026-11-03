"""
Tests for ingestion: text splitter behavior and content hashing.

The splitter must normalize text, split at Persian sentence boundaries, avoid
duplicate chunks, and preserve section headings.
"""

from app.core.domain import Document
from app.infrastructure.text_splitter import LangChainTextSplitter


def make_splitter(chunk_size: int = 80, chunk_overlap: int = 10):
    return LangChainTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def test_split_returns_empty_for_no_documents():
    assert make_splitter().split([]) == []


def test_split_strips_bom_from_chunks():
    """BOM must never reach the vector store."""
    doc = Document(content="\ufeffمتن اول. متن دوم.", metadata={"source": "a.txt"})
    chunks = make_splitter().split([doc])

    assert chunks
    assert all("\ufeff" not in c.text for c in chunks)


def test_split_normalizes_crlf():
    """Windows line endings must be normalized away."""
    doc = Document(content="line one\r\nline two", metadata={"source": "a.txt"})
    chunks = make_splitter().split([doc])

    assert chunks
    assert all("\r" not in c.text for c in chunks)


def test_split_respects_chunk_size():
    """Chunks stay within the configured size (plus small boundary slack)."""
    text = "این یک جمله آزمایشی است. " * 30
    doc = Document(content=text, metadata={"source": "a.txt"})

    chunks = make_splitter(chunk_size=100, chunk_overlap=10).split([doc])

    assert len(chunks) > 1
    for chunk in chunks:
        # Allow a small margin for separator handling.
        assert len(chunk.text) <= 110


def test_split_assigns_content_hash():
    """Every chunk carries a content hash for duplicate detection."""
    doc = Document(content="متن نمونه برای هش.", metadata={"source": "a.txt"})
    chunks = make_splitter().split([doc])

    assert chunks
    assert all(c.metadata.get("content_hash") for c in chunks)


def test_split_deduplicates_identical_chunks():
    """Two identical documents must not produce duplicate chunk texts."""
    doc = Document(content="محتوای یکسان تکراری.", metadata={"source": "a.txt"})
    chunks = make_splitter().split([doc, doc])

    texts = [c.text for c in chunks]
    assert len(texts) == len(set(texts))


def test_split_prefixes_heading_when_present():
    """A markdown section heading is prepended so chunks keep context."""
    doc = Document(
        content="محتوای بخش اول درباره یکسوکننده.",
        metadata={"source": "a.md", "header_1": "بلوک‌شناسی"},
    )
    chunks = make_splitter().split([doc])

    assert chunks
    assert chunks[0].text.startswith("بلوک‌شناسی")


def test_split_skips_whitespace_only_documents():
    """Empty documents produce no chunks."""
    doc = Document(content="   \n\n  ", metadata={"source": "a.txt"})
    assert make_splitter().split([doc]) == []


def test_split_generates_unique_ids():
    """Chunk ids must be unique across a batch."""
    doc = Document(content="جمله اول. جمله دوم. جمله سوم.", metadata={"source": "a.txt"})
    chunks = make_splitter(chunk_size=20, chunk_overlap=5).split([doc])

    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
