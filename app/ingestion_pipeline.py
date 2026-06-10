"""
Ingestion pipeline for the RAG system using LangChain.

This module orchestrates the full ingestion workflow: load JSON,
split into chunks using LangChain's text splitter, and store in
the LangChain Chroma vector store.
"""

import logging
from typing import List

from langchain_core.documents import Document

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
        Ingest a JSON file: load, chunk, and store.

        Uses LangChain's Document objects throughout the pipeline.
        When an embedding_function is configured on the vector store,
        embeddings are generated automatically.

        Args:
            file_path: Path to the JSON file to ingest.

        Returns:
            Number of chunks ingested.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        # Step 1: Load documents (returns LangChain Document objects)
        documents = self.loader.load(file_path)
        logger.info("Loaded %d documents from %s", len(documents), file_path)

        if not documents:
            logger.warning("No documents found in %s", file_path)
            return 0

        # Step 2: Split documents into chunks
        chunks: List[Document] = self.text_splitter.split_documents(documents)
        logger.info("Split into %d chunks", len(chunks))

        if not chunks:
            logger.warning("No chunks generated")
            return 0

        # Step 3: Store in vector database
        # Generate IDs for each chunk
        ids = [f"doc_{i}" for i in range(len(chunks))]

        # If the vector store has an embedding function, use add_documents
        # which will auto-generate embeddings; otherwise embed manually
        if self.vector_store.vector_store._embedding_function is not None:
            self.vector_store._vector_store.add_documents(
                documents=chunks, ids=ids
            )
        else:
            texts = [doc.page_content for doc in chunks]
            embeddings = self.embedding_service.embed_batch(texts)
            self.vector_store.add_documents(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=[doc.metadata for doc in chunks],
            )

        logger.info("Stored %d chunks in vector store", len(chunks))

        return len(chunks)
