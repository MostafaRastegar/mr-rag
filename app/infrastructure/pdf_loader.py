"""
PDF Document Loader.

Implements the DocumentLoaderPort interface for PDF files using PyMuPDF (fitz).
Extracts text from PDF pages and returns them as Document objects.
"""

import logging
from pathlib import Path
from typing import List

from app.core.domain import Document
from app.core.exceptions import DocumentLoadError
from app.core.ports import DocumentLoaderPort

logger = logging.getLogger(__name__)


class PDFDocumentLoader(DocumentLoaderPort):
    """
    Loads documents from PDF files using PyMuPDF (fitz).

    Extracts text from each page and returns a list of Document objects,
    one per page. Metadata includes page number and total page count.
    """

    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            A list of Document objects, one per page.

        Raises:
            DocumentLoadError: If the file cannot be read or parsed.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise DocumentLoadError(
                "PyMuPDF (fitz) is not installed. Install it with: pip install pymupdf"
            ) from e

        try:
            doc = fitz.open(file_path)
            documents: List[Document] = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                if not text.strip():
                    logger.warning("Empty page %d in %s", page_num + 1, file_path)
                    continue

                metadata = {
                    "source": path.name,
                    "page": page_num + 1,
                    "total_pages": len(doc),
                }

                documents.append(
                    Document(content=text.strip(), metadata=metadata)
                )

            doc.close()

            logger.info(
                "Loaded %d pages from %s using PyMuPDF",
                len(documents),
                file_path,
            )
            return documents

        except Exception as e:
            raise DocumentLoadError(f"Failed to load PDF from {file_path}: {e}") from e