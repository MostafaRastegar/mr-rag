"""
JSON Document Loader.

Implements the DocumentLoaderPort interface to load documents
from JSON scraper output files.
"""

import json
import logging
from pathlib import Path
from typing import List

from app.core.domain import Document
from app.core.exceptions import DocumentLoadError
from app.core.ports import DocumentLoaderPort

logger = logging.getLogger(__name__)


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
