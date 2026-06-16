"""
Document Loaders.

Implements the DocumentLoaderPort interface using LangChain's
document loaders for JSON, Markdown, and plain text files.
"""

import json
import logging
from pathlib import Path
from typing import Any, List

from langchain_community.document_loaders import JSONLoader, TextLoader

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


# ---------------------------------------------------------------------------
# JSON Loader (LangChain JSONLoader)
# ---------------------------------------------------------------------------


def _json_metadata_func(record: dict, metadata: dict) -> dict:
    """
    Extract metadata from a JSON record, excluding content/text fields.

    Args:
        record: The original JSON object from the file.
        metadata: Any pre-existing metadata from the loader.

    Returns:
        Updated metadata dict with all non-content fields.
    """
    for k, v in record.items():
        if k not in ("content", "text"):
            metadata[k] = v
    return metadata


class JsonDocumentLoader(DocumentLoaderPort):
    """
    Loads documents from JSON files using LangChain's JSONLoader.

    Expected JSON format: a list of objects (or a single object), each with
    at least a 'content' or 'text' field. Additional fields like 'title',
    'url', 'source' are kept as metadata.

    Uses jq schema internally for robust field extraction.
    """

    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a JSON file using LangChain's JSONLoader.

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
            # First, inspect the JSON structure to determine the jq schema
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Normalize: if it's a single dict, wrap it in a list
            if isinstance(raw_data, dict):
                raw_data = [raw_data]

            # Use LangChain's JSONLoader with a schema that extracts
            # the content field plus all metadata via metadata_func
            loader = JSONLoader(
                file_path=str(path),
                jq_schema=".[]",
                content_key='.content // .text // ""',
                metadata_func=_json_metadata_func,
                text_content=False,
            )

            lc_documents = loader.load()

        except json.JSONDecodeError as e:
            raise DocumentLoadError(f"Invalid JSON in {file_path}: {e}") from e
        except OSError as e:
            raise DocumentLoadError(f"Cannot read {file_path}: {e}") from e
        except Exception as e:
            raise DocumentLoadError(f"Failed to load JSON from {file_path}: {e}") from e

        # Convert LangChain Documents to domain Documents
        documents = [
            Document(content=doc.page_content, metadata=dict(doc.metadata))
            for doc in lc_documents
            if doc.page_content.strip()
        ]

        logger.info(
            "Loaded %d documents from %s using LangChain JSONLoader",
            len(documents),
            file_path,
        )
        return documents


# ---------------------------------------------------------------------------
# Markdown Loader (LangChain TextLoader + MarkdownHeaderTextSplitter)
# ---------------------------------------------------------------------------


class MarkdownDocumentLoader(DocumentLoaderPort):
    """
    Loads documents from markdown (.md) files, splitting by sections
    using LangChain's MarkdownHeaderTextSplitter.

    Each heading (## or deeper) starts a new Document. Content before
    the first heading is captured as a preamble Document.

    Metadata includes:
        - source: file name
        - section: heading hierarchy path
        - heading_level: depth of the heading (1 for #, 2 for ##, etc.)
    """

    def __init__(self) -> None:
        from langchain_text_splitters import MarkdownHeaderTextSplitter

        self._splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header_1"),
                ("##", "header_2"),
                ("###", "header_3"),
                ("####", "header_4"),
                ("#####", "header_5"),
                ("######", "header_6"),
            ],
            strip_headers=False,
        )

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

        try:
            # Split markdown by headers using LangChain's splitter
            lc_docs = self._splitter.split_text(raw)
        except Exception as e:
            raise DocumentLoadError(f"Failed to split markdown {file_path}: {e}") from e

        if not lc_docs:
            # No headings found → treat as plain text
            metadata = {"source": path.name, "section": "root", "heading_level": 0}
            return [Document(content=raw.strip(), metadata=metadata)]

        # Convert LangChain Documents to domain Documents
        documents: List[Document] = []
        for lc_doc in lc_docs:
            metadata = dict(lc_doc.metadata)
            metadata["source"] = path.name
            documents.append(
                Document(content=lc_doc.page_content.strip(), metadata=metadata)
            )

        logger.info(
            "Loaded %d sections from %s using LangChain MarkdownHeaderTextSplitter",
            len(documents),
            file_path,
        )
        return documents


# ---------------------------------------------------------------------------
# Plain Text Loader (LangChain TextLoader)
# ---------------------------------------------------------------------------


class TextDocumentLoader(DocumentLoaderPort):
    """Loads documents from plain text (.txt) files using LangChain's TextLoader."""

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
            loader = TextLoader(file_path=str(path), encoding="utf-8")
            lc_docs = loader.load()
        except OSError as e:
            raise DocumentLoadError(f"Cannot read {file_path}: {e}") from e
        except Exception as e:
            raise DocumentLoadError(f"Failed to load text from {file_path}: {e}") from e

        if not lc_docs or not lc_docs[0].page_content.strip():
            logger.warning("Empty text file: %s", file_path)
            return []

        # Convert to domain Document
        lc_doc = lc_docs[0]
        documents = [
            Document(
                content=lc_doc.page_content.strip(),
                metadata={"source": path.name, **dict(lc_doc.metadata)},
            )
        ]

        logger.info("Loaded 1 document from %s using LangChain TextLoader", file_path)
        return documents


# ---------------------------------------------------------------------------
# Auto Loader (dispatches by file extension)
# ---------------------------------------------------------------------------


class AutoDocumentLoader(DocumentLoaderPort):
    """
    Composite document loader that selects the appropriate LangChain-based
    loader based on the file extension of the input path.

    Supported formats:
        - .json  → JsonDocumentLoader (LangChain JSONLoader)
        - .md    → MarkdownDocumentLoader (LangChain MarkdownHeaderTextSplitter)
        - .txt   → TextDocumentLoader (LangChain TextLoader)
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
