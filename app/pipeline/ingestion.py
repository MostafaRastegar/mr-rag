"""
Ingestion Pipeline.

Orchestrates the full document ingestion workflow:
load → split → embed → store.
Depends only on abstract ports, not on concrete implementations.
"""

import logging
from typing import List

from app.core.domain import Chunk, Document
from app.core.exceptions import IngestionError
from app.core.ports import (
    DocumentLoaderPort,
    EmbeddingPort,
    TextSplitterPort,
    VectorStorePort,
)

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
    ) -> None:
        self._loader = loader
        self._splitter = splitter
        self._embedding = embedding
        self._vector_store = vector_store

    def run(self, file_path: str) -> int:
        """
        Ingest a file: load documents, split into chunks, embed, and store.

        Args:
            file_path: Path to the source file to ingest.

        Returns:
            Number of chunks ingested.

        Raises:
            IngestionError: If any step of the pipeline fails.
            DocumentLoadError: If the file cannot be loaded.
        """
        logger.info("Starting ingestion from: %s", file_path)

        # Step 1: Load documents
        documents: List[Document] = self._loader.load(file_path)
        if not documents:
            logger.warning("No documents found in %s", file_path)
            return 0
        logger.info("Loaded %d documents", len(documents))

        # Step 2: Split into chunks
        chunks: List[Chunk] = self._splitter.split(documents)
        if not chunks:
            logger.warning("No chunks generated from %d documents", len(documents))
            return 0
        logger.info("Split into %d chunks", len(chunks))

        # Step 3: Generate embeddings
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

        # Step 4: Store in vector store
        try:
            stored = self._vector_store.add(chunks, embeddings)
        except Exception as e:
            logger.error("Vector store insertion failed: %s", str(e))
            raise IngestionError(f"Failed to store chunks: {e}") from e

        logger.info("Ingestion complete: %d chunks stored", stored)
        return stored
