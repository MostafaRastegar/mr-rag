"""
Text normalization utilities for ingestion.

Raw source documents carry artifacts that silently degrade retrieval quality
and waste context tokens:

  - UTF-8 BOM (U+FEFF) left by Windows editors, which pollutes the first
    chunk and skews its embedding.
  - CRLF line endings, which make line-joined text harder to read and inflate
    token counts.
  - Vertical tab / form feed characters extracted from PDFs.
  - Repeated blank lines, which waste the model's context window.

Normalizing once at ingestion time keeps the vector store, the BM25 index and
the LLM context consistent — the same text is compared everywhere.

This module is intentionally dependency-free so both the loaders and any
future pipeline stage can reuse it.
"""

import logging
import re

logger = logging.getLogger(__name__)

# BOM variants that appear at the start of UTF-8 files.
_BOM = "\ufeff"

# Two or more blank lines (allowing for spaces/tabs in between).
_MULTI_BLANK_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")

# Runs of spaces/tabs (but not newlines, which carry structure).
_INLINE_WHITESPACE = re.compile(r"[ \t\u00a0]{2,}")


def normalize_text(text: str) -> str:
    """
    Normalize raw document text for storage and retrieval.

    Applies, in order:
      1. Strip UTF-8 BOM characters anywhere in the string.
      2. Normalize line endings to ``\\n`` (CRLF and lone CR).
      3. Remove vertical tab / form feed.
      4. Collapse runs of horizontal whitespace to a single space.
      5. Collapse 3+ consecutive newlines to a paragraph break.
      6. Strip leading/trailing whitespace.

    Arabic/Persian letter variants are deliberately NOT unified here: that
    mapping is for token matching (see the BM25 preprocessor), and rewriting
    document text would alter quoted values such as part numbers.

    Args:
        text: Raw text from a loader.

    Returns:
        The normalized text. Returns an empty string for empty input.
    """
    if not text:
        return ""

    normalized = text.replace(_BOM, "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\x0b", "\n").replace("\x0c", "\n")
    normalized = _INLINE_WHITESPACE.sub(" ", normalized)
    normalized = _MULTI_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()


def content_hash(text: str) -> str:
    """
    Compute a stable content hash for duplicate detection.

    The hash is computed over the normalized text so trivial whitespace
    differences between two ingests of the same source do not produce
    different hashes.

    Args:
        text: Chunk or document text.

    Returns:
        A short hexadecimal digest.
    """
    import hashlib

    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:16]
