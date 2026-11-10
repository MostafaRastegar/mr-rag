"""
Ingestion Pipeline.

Orchestrates the full document ingestion workflow:
load → split → embed → store.
Depends only on abstract ports, not on concrete implementations.
"""

import logging
import time
import uuid
from pathlib import Path
from typing import List

from app.core.domain import Chunk, Document, DocumentInfo
from app.core.exceptions import IngestionError
from app.core.ports import (
    DocumentLoaderPort,
    DocumentRepositoryPort,
    EmbeddingPort,
    TextSplitterPort,
    VectorStorePort,
)
from app.config import settings
from app.infrastructure.vision_llm import describe_image, vision_llm

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Orchestrates the document ingestion process.

    Follows the Dependency Inversion Principle: depends on
    abstract ports injected at construction time.
    """

    def __init__(
        self,
        loader: DocumentLoaderPort,
        splitter: TextSplitterPort,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
        doc_repo: DocumentRepositoryPort | None = None,
    ) -> None:
        self._loader = loader
        self._splitter = splitter
        self._embedding = embedding
        self._vector_store = vector_store
        self._doc_repo = doc_repo

    def run_documents(
        self,
        documents: List[Document],
        original_filename: str | None = None,
        source_path: str | None = None,
        extra_chunks: List[Chunk] | None = None,
    ) -> int:
        """
        Ingest already-loaded documents: split → embed → store → save metadata.

        Args:
            documents: Loaded documents to ingest.
            original_filename: Logical origin name (used for delete-by-metadata).
            source_path: Logical source path stored in chunk metadata.
            extra_chunks: Additional chunks (e.g. image descriptions) to embed
                and store alongside the split text chunks.

        Returns:
            Number of chunks ingested.
        """
        if not documents and not extra_chunks:
            logger.warning("No documents or extra chunks provided")
            return 0
        logger.info("Ingesting %d documents", len(documents))

        # Step 1: Split into chunks
        chunks: List[Chunk] = self._splitter.split(documents) if documents else []
        if extra_chunks:
            chunks.extend(extra_chunks)
        if not chunks:
            logger.warning("No chunks generated from %d documents", len(documents))
            return 0
        logger.info("Split into %d chunks", len(chunks))

        # Step 2: Generate embeddings
        try:
            texts = [chunk.text for chunk in chunks]
            embeddings = self._embedding.embed_documents(texts)
        except Exception as e:
            logger.error("Embedding generation failed: %s", str(e))
            raise IngestionError(f"Failed to generate embeddings: {e}") from e

        if len(embeddings) != len(chunks):
            raise IngestionError(
                f"Embedding count mismatch: got {len(embeddings)} embeddings "
                f"for {len(chunks)} chunks"
            )

        orig_name = original_filename or "documents"
        src_path = source_path or orig_name
        for chunk in chunks:
            if "original_filename" not in chunk.metadata:
                chunk.metadata["original_filename"] = orig_name
            if "source_path" not in chunk.metadata:
                chunk.metadata["source_path"] = str(src_path)

        # Step 3: Store in vector store
        try:
            stored = self._vector_store.add(chunks, embeddings)
        except Exception as e:
            logger.error("Vector store insertion failed: %s", str(e))
            raise IngestionError(f"Failed to store chunks: {e}") from e

        logger.info("Ingestion complete: %d chunks stored", stored)

        # Step 4: Save document metadata (optional)
        if self._doc_repo is not None:
            try:
                doc_info = DocumentInfo(
                    id=str(uuid.uuid4()),
                    filename=Path(src_path).name or orig_name,
                    original_filename=orig_name,
                    source_path=str(src_path),
                    file_type="confluence" if orig_name.startswith("confluence:") else "",
                    chunk_count=stored,
                    ingested_at=time.time(),
                )
                self._doc_repo.save(doc_info)
                logger.info("Saved document metadata: %s (%s)", doc_info.id, doc_info.filename)
            except Exception as e:
                logger.warning("Failed to save document metadata: %s", e)

        return stored

    def run(self, file_path: str, original_filename: str | None = None) -> int:
        """
        Ingest a file: load documents, split into chunks, embed, and store.

        Args:
            file_path: Path to the source file to ingest.
            original_filename: Original file name (before rename to temp).

        Returns:
            Number of chunks ingested.

        Raises:
            IngestionError: If any step of the pipeline fails.
            DocumentLoadError: If the file cannot be loaded.
        """
        logger.info("Starting ingestion from: %s", file_path)

        # Check if file is a standalone image
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
        file_ext = Path(file_path).suffix.lower()
        is_standalone_image = file_ext in image_extensions

        if is_standalone_image:
            if settings.vision_enabled:
                # Fail fast if OpenRouter is unreachable, consistent with PDF vision path.
                if not vision_llm.ping():
                    logger.warning(
                        "Vision LLM ping failed — skipping standalone image description"
                    )
                    return 0
                # Handle standalone image file directly (describe with VLM, store as chunk)
                try:
                    import base64

                    image_path = Path(file_path)
                    image_bytes = image_path.read_bytes()
                    ext = image_path.suffix.lstrip(".").lower()
                    mime_type = f"image/{'jpeg' if ext == 'jpg' else ext}"

                    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                    description = describe_image(image_b64, mime_type)
                    image_ref = str(uuid.uuid4())

                    image_chunk = Chunk(
                        id=image_ref,
                        text=f"[توضیح تصویر] {description}",
                        metadata={
                            "source": image_path.name,
                            "page": 1,
                            "image_index": 0,
                            "image_ref": image_ref,
                            "image_path": str(image_path),
                            "original_filename": original_filename or image_path.name,
                            "source_path": file_path,
                            "chunk_type": "image",
                        },
                        chunk_type="image",
                        image_ref=image_ref,
                    )

                    logger.info("Described standalone image: %s", image_path.name)
                    return self.run_documents(
                        [],
                        original_filename=original_filename,
                        source_path=file_path,
                        extra_chunks=[image_chunk],
                    )

                except Exception as e:
                    logger.warning("Failed to describe standalone image %s: %s", file_path, e)
                    return 0
            else:
                logger.warning("Image upload without vision enabled — skipping")
                return 0

        # Step 1: Load documents
        documents: List[Document] = self._loader.load(file_path)
        if not documents:
            logger.warning("No documents found in %s", file_path)
            return 0
        logger.info("Loaded %d documents", len(documents))

        # Step 1.5: Process images with VLM if enabled
        extra_chunks: List[Chunk] = []
        if settings.vision_enabled:
            logger.info("Vision enabled — processing images with VLM")
            try:
                import fitz  # PyMuPDF
            except ImportError as e:
                logger.warning("PyMuPDF not installed — skipping image processing: %s", e)
                fitz = None

            if fitz is not None:
                try:
                    doc = fitz.open(file_path)
                    # Phase 1 — scan once, collect every candidate image (local, no network).
                    source = Path(file_path).name
                    image_map: list[dict] = []
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        page_label = page_num + 1

                        # --- Embedded raster images (photos, etc.) ---
                        images = page.get_images(full=True)
                        for img_idx, img in enumerate(
                            images[: settings.vision_max_images_per_page]
                        ):
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            ext = base_image.get("ext", "png")
                            mime_type = f"image/{ext}"
                            image_map.append(
                                {
                                    "page_label": page_label,
                                    "img_idx": img_idx,
                                    "image_bytes": image_bytes,
                                    "mime_type": mime_type,
                                    "source": source,
                                    "is_page_render": False,
                                }
                            )

                        # --- Full-page render (captures vector drawings / geometry) ---
                        if settings.vision_render_pages:
                            pix = page.get_pixmap(dpi=settings.vision_render_dpi)
                            image_bytes = pix.tobytes("png")
                            image_map.append(
                                {
                                    "page_label": page_label,
                                    "img_idx": -1,
                                    "image_bytes": image_bytes,
                                    "mime_type": "image/png",
                                    "source": source,
                                    "is_page_render": True,
                                }
                            )
                    doc.close()

                    # Optional: persist extracted images with meaningful names for debugging/reuse.
                    extract_dir = Path(settings.vision_extract_dir)
                    if settings.vision_extract_dir:
                        extract_dir.mkdir(parents=True, exist_ok=True)
                        for entry in image_map:
                            safe_name = (
                                f"{Path(file_path).stem}_p{entry['page_label']}_"
                                f"img{entry['img_idx']}.{entry['mime_type'].split('/')[-1]}"
                            )
                            img_path = extract_dir / safe_name
                            img_path.write_bytes(entry["image_bytes"])
                            entry["image_path"] = str(img_path)

                    # Phase 2 — fail-fast health check before any VLM call.
                    if not vision_llm.ping():
                        logger.warning(
                            "Vision LLM ping failed — skipping image descriptions"
                        )
                    else:
                        # Phase 3 — describe images concurrently so large PDFs don't block upload.
                        import base64
                        from concurrent.futures import ThreadPoolExecutor, as_completed

                        def describe_one(entry: dict):
                            try:
                                image_b64 = base64.b64encode(
                                    entry["image_bytes"]
                                ).decode("utf-8")
                                description = describe_image(
                                    image_b64, entry["mime_type"]
                                )
                                image_ref = str(uuid.uuid4())
                                return Chunk(
                                    id=image_ref,
                                    text=(
                                        f"[توضیح تصویر صفحه {entry['page_label']}] {description}"
                                    ),
                                    metadata={
                                        "source": entry["source"],
                                        "page": entry["page_label"],
                                        "image_index": entry["img_idx"],
                                        "image_ref": image_ref,
                                        "image_path": entry.get("image_path"),
                                        "original_filename": original_filename or entry["source"],
                                        "source_path": file_path,
                                        "chunk_type": "image",
                                    },
                                    chunk_type="image",
                                    image_ref=image_ref,
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to describe image %d on page %d: %s",
                                    entry["img_idx"],
                                    entry["page_label"],
                                    e,
                                )
                                return None

                        max_workers = max(1, settings.vision_max_concurrency)
                        with ThreadPoolExecutor(max_workers=max_workers) as pool:
                            futures = [
                                pool.submit(describe_one, entry) for entry in image_map
                            ]
                            for future in as_completed(futures):
                                chunk = future.result()
                                if chunk is not None:
                                    extra_chunks.append(chunk)
                                    logger.info(
                                        "Described image %d on page %d",
                                        chunk.metadata["image_index"],
                                        chunk.metadata["page"],
                                    )
                except Exception as e:
                    logger.warning("Failed to open PDF for vision processing: %s", e)

        return self.run_documents(
            documents,
            original_filename=original_filename,
            source_path=file_path,
            extra_chunks=extra_chunks,
        )
