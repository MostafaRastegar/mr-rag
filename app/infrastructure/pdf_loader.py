"""
PDF Document Loader.

Implements the DocumentLoaderPort interface for PDF files using PyMuPDF (fitz).
Extracts text from PDF pages and returns them as Document objects.

Note: Embedded image binary data is NOT stored in Document metadata because
ChromaDB only accepts scalar metadata values (str, int, float, bool) and
homogeneous lists. If vision processing is enabled, the ingestion pipeline
extracts images directly from the file.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, List

from app.core.domain import Document
from app.core.exceptions import DocumentLoadError
from app.core.ports import DocumentLoaderPort
from app.config import settings

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

                # Count embedded images on this page (simple scalar for metadata)
                try:
                    image_count = len(page.get_images(full=True))
                except Exception:
                    image_count = 0

                if not text.strip() and image_count == 0:
                    logger.warning("Empty page %d in %s", page_num + 1, file_path)
                    continue

                metadata = {
                    "source": path.name,
                    "page": page_num + 1,
                    "total_pages": len(doc),
                    "image_count": image_count,
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

    # -----------------------------------------------------------------------
    # Streaming loader — yields one Document per page (memory-efficient).
    # -----------------------------------------------------------------------

    def load_streamed(self, file_path: str) -> Iterator[Document]:
        """
        Lazily yield Document objects, one per PDF page.

        Unlike ``load`` this does not build the full list in RAM, which is
        critical for multi-hundred-page PDFs. Callers can stop early if a
        single page is malformed without aborting the whole upload.

        Args:
            file_path: Path to the PDF file.

        Yields:
            Document objects (one per non-empty page).

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

        doc = None
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                try:
                    image_count = len(page.get_images(full=True))
                except Exception:
                    image_count = 0

                if not text.strip() and image_count == 0:
                    logger.warning("Empty page %d in %s", page_num + 1, file_path)
                    continue

                metadata = {
                    "source": path.name,
                    "page": page_num + 1,
                    "total_pages": len(doc),
                    "image_count": image_count,
                }

                yield Document(content=text.strip(), metadata=metadata)
        except Exception as e:
            raise DocumentLoadError(f"Failed to stream PDF from {file_path}: {e}") from e
        finally:
            if doc is not None:
                doc.close()

    # -----------------------------------------------------------------------
    # Parallel loader — splits pages across worker threads.
    # -----------------------------------------------------------------------

    def _extract_page_range(
        self, file_path: str, start: int, end: int, source_name: str
    ) -> List[Document]:
        """
        Extract a contiguous page range [start, end) from a PDF.

        Each call opens its own fitz handle because PyMuPDF documents are
        not thread-safe.
        """
        import fitz  # PyMuPDF

        docs: List[Document] = []
        doc = fitz.open(file_path)
        try:
            for page_num in range(start, min(end, len(doc))):
                page = doc[page_num]
                text = page.get_text()

                try:
                    image_count = len(page.get_images(full=True))
                except Exception:
                    image_count = 0

                if not text.strip() and image_count == 0:
                    continue

                metadata = {
                    "source": source_name,
                    "page": page_num + 1,
                    "total_pages": len(doc),
                    "image_count": image_count,
                }
                docs.append(Document(content=text.strip(), metadata=metadata))
        finally:
            doc.close()
        return docs

    def load_parallel(
        self, file_path: str, max_workers: int | None = None
    ) -> List[Document]:
        """
        Load PDF pages in parallel using a thread pool.

        Splits the document into page ranges and assigns each range to a
        worker thread. Safe for PyMuPDF because every thread opens its own
        document handle.

        Args:
            file_path: Path to the PDF file.
            max_workers: Number of threads. Defaults to settings.pdf_parallel_workers.

        Returns:
            List of Document objects sorted by page number.

        Raises:
            DocumentLoadError: If the file cannot be read or parsed.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentLoadError(f"File not found: {file_path}")

        workers = max_workers or settings.pdf_parallel_workers

        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise DocumentLoadError(
                "PyMuPDF (fitz) is not installed. Install it with: pip install pymupdf"
            ) from e

        # Get total page count (open once, close immediately)
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()
        except Exception as e:
            raise DocumentLoadError(f"Failed to open PDF {file_path}: {e}") from e

        if total_pages == 0:
            return []

        # Split into contiguous ranges
        chunk_size = max(1, total_pages // workers)
        ranges: list[tuple[int, int]] = []
        for i in range(0, total_pages, chunk_size):
            ranges.append((i, min(i + chunk_size, total_pages)))

        # Cap workers to number of ranges
        actual_workers = min(workers, len(ranges))

        results: List[Document] = []
        try:
            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                futures = [
                    executor.submit(
                        self._extract_page_range,
                        file_path,
                        start,
                        end,
                        path.name,
                    )
                    for start, end in ranges
                ]
                for future in as_completed(futures):
                    results.extend(future.result())
        except Exception as e:
            raise DocumentLoadError(
                f"Parallel PDF load failed for {file_path}: {e}"
            ) from e

        # Restore page order
        results.sort(key=lambda d: d.metadata.get("page", 0))

        logger.info(
            "Loaded %d pages from %s using parallel PyMuPDF (%d workers)",
            len(results),
            file_path,
            actual_workers,
        )
        return results
