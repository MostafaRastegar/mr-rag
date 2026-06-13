"""
Document Loaders.

Implements the DocumentLoaderPort interface to load documents
from various file formats (JSON, TXT, etc.).
"""

import json
import logging
import re
from pathlib import Path
from typing import List

from app.core.domain import Document
from app.core.exceptions import DocumentLoadError
from app.core.ports import DocumentLoaderPort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".json": "JSON",
    ".md": "Markdown",
    ".txt": "Plain Text",
}

# Regex pattern to match markdown headings (##, ###, etc.)
_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# JSON Loader
# ---------------------------------------------------------------------------


class JsonDocumentLoader(DocumentLoaderPort):
    """Loads documents from JSON scraper output files."""

    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a JSON file.

        Expected JSON format: a list of objects, each with at
        least a 'content' or 'text' field. Additional fields
        like 'title', 'url', 'source' are kept as metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            A list of Document objects.

        Raises:
            DocumentLoadError: If the file cannot be loaded or parsed.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise DocumentLoadError(f"Invalid JSON in {file_path}: {e}") from e
        except OSError as e:
            raise DocumentLoadError(f"Cannot read {file_path}: {e}") from e

        if isinstance(data, dict):
            data = [data]

        documents: List[Document] = []
        for item in data:
            content = item.get("content") or item.get("text") or ""
            if not content:
                continue

            metadata = {k: v for k, v in item.items() if k not in ("content", "text")}
            documents.append(Document(content=content, metadata=metadata))

        logger.info("Loaded %d documents from %s", len(documents), file_path)
        return documents


# ---------------------------------------------------------------------------
# Markdown Loader (splits by headings)
# ---------------------------------------------------------------------------


class MarkdownDocumentLoader(DocumentLoaderPort):
    """
    Loads documents from markdown (.md) files, splitting by sections.

    Each heading (## or deeper) starts a new Document. Content before the
    first heading is captured as a preamble Document.

    Metadata includes:
        - source: file name
        - section: heading hierarchy path (e.g. "Quick Start > 1. Environment Setup")
        - heading_level: depth of the heading (2 for ##, 3 for ###, etc.)
    """

    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a markdown file, one per section.

        Args:
            file_path: Path to the .md file.

        Returns:
            A list of Document objects, one per markdown section.

        Raises:
            DocumentLoadError: If the file cannot be read.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            raise DocumentLoadError(f"Cannot read {file_path}: {e}") from e

        if not raw.strip():
            logger.warning("Empty markdown file: %s", file_path)
            return []

        # Find all heading positions
        heading_matches = list(_HEADING_RE.finditer(raw))
        if not heading_matches:
            # No headings → treat as plain text
            metadata = {"source": path.name, "section": "root", "heading_level": 0}
            return [Document(content=raw.strip(), metadata=metadata)]

        documents: List[Document] = []

        # Capture content before the first heading (title / preamble)
        first_heading_start = heading_matches[0].start()
        preamble = raw[:first_heading_start].strip()
        if preamble:
            metadata = {
                "source": path.name,
                "section": "preamble",
                "heading_level": 0,
            }
            documents.append(Document(content=preamble, metadata=metadata))

        # Track heading hierarchy for building section paths
        heading_stack: list[tuple[int, str]] = []  # [(level, title), ...]

        for i, match in enumerate(heading_matches):
            level = len(match.group(1))  # number of # characters
            title = match.group(2).strip()
            start = match.end() + 1  # content starts after the heading line
            end = (
                heading_matches[i + 1].start()
                if i + 1 < len(heading_matches)
                else len(raw)
            )

            content = raw[start:end].strip()

            # Update heading stack: pop headings at same or deeper level
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

            # Build section path
            section_path = " > ".join(h[1] for h in heading_stack)

            metadata = {
                "source": path.name,
                "section": section_path,
                "heading_level": level,
            }
            documents.append(Document(content=content, metadata=metadata))

        logger.info("Loaded %d sections from %s", len(documents), file_path)
        return documents


# ---------------------------------------------------------------------------
# Plain Text Loader
# ---------------------------------------------------------------------------


class TextDocumentLoader(DocumentLoaderPort):
    """Loads documents from plain text (.txt) files."""

    def load(self, file_path: str) -> List[Document]:
        """
        Load a single document from a plain text file.

        The entire file content becomes one Document. The file name
        is stored as metadata under the 'source' key.

        Args:
            file_path: Path to the .txt file.

        Returns:
            A list containing a single Document object.

        Raises:
            DocumentLoadError: If the file cannot be read.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise DocumentLoadError(f"Cannot read {file_path}: {e}") from e

        if not content.strip():
            logger.warning("Empty text file: %s", file_path)
            return []

        metadata = {"source": path.name}
        documents = [Document(content=content.strip(), metadata=metadata)]

        logger.info("Loaded 1 document from %s", file_path)
        return documents


# ---------------------------------------------------------------------------
# Auto Loader (dispatches by file extension)
# ---------------------------------------------------------------------------


class AutoDocumentLoader(DocumentLoaderPort):
    """
    Composite document loader that selects the appropriate loader
    based on the file extension of the input path.

    Supported formats:
        - .json  → JsonDocumentLoader
        - .md    → MarkdownDocumentLoader
        - .txt   → TextDocumentLoader
    """

    def __init__(self) -> None:
        self._loaders: dict[str, DocumentLoaderPort] = {
            ".json": JsonDocumentLoader(),
            ".md": MarkdownDocumentLoader(),
            ".txt": TextDocumentLoader(),
        }

    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a file, auto-detecting the format
        from the file extension.

        Args:
            file_path: Path to the source file.

        Returns:
            A list of Document objects.

        Raises:
            DocumentLoadError: If the file extension is not supported
                               or the underlying loader fails.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        loader = self._loaders.get(ext)
        if loader is None:
            supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS.values()))
            raise DocumentLoadError(
                f"Unsupported file extension '{ext}' for {file_path}. "
                f"Supported formats: {supported}"
            )

        logger.info(
            "Auto-detected format '%s' for %s", _SUPPORTED_EXTENSIONS[ext], file_path
        )
        return loader.load(file_path)
