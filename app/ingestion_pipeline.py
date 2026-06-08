"""
Ingestion pipeline for the RAG system.

This module orchestrates the full ingestion workflow: load JSON,
split into chunks, generate embeddings, and store in ChromaDB.
"""

import logging
from typing import List

from app.config import settings
from app.document_loader import DocumentLoader
from app.text_splitter import create_text_splitter
from app.embedding_service import EmbeddingService
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the document ingestion process."""

    def __init__(
        self,
        loader: DocumentLoader,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.loader = loader
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.text_splitter = create_text_splitter()

    def run(self, file_path: str) -> int:
        """
        Ingest a JSON file: load, chunk, embed, and store.

        Args:
            file_path: Path to the JSON file to ingest.

        Returns:
            Number of chunks ingested.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        # Step 1: Load raw documents
        documents = self.loader.load(file_path)
        logger.info("Loaded %d documents from %s", len(documents), file_path)

        if not documents:
            logger.warning("No documents found in %s", file_path)
            return 0

        # Step 2: Chunk documents
        all_chunks: List[str] = []
        all_metadatas: List[dict] = []

        for doc in documents:
            chunks = self.text_splitter.split_text(doc["content"])
            metadata = doc.get("metadata", {})

            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append(metadata)

        logger.info("Split into %d chunks", len(all_chunks))

        if not all_chunks:
            logger.warning("No chunks generated")
            return 0

        # Step 3: Generate embeddings
        embeddings = self.embedding_service.embed_batch(all_chunks)
        logger.info("Generated %d embeddings", len(embeddings))

        # Step 4: Store in vector database
        ids = [f"doc_{i}" for i in range(len(all_chunks))]
        self.vector_store.add_documents(
            ids=ids,
            embeddings=embeddings,
            documents=all_chunks,
            metadatas=all_metadatas,
        )
        logger.info("Stored %d chunks in vector store", len(all_chunks))

        return len(all_chunks)