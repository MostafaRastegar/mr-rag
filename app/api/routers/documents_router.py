"""
Document management routes: /documents/*.

Thin layer — delegates to document repository and vector store.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    DocumentDeleteResponse,
    DocumentItem,
    DocumentListResponse,
)
from app.core.exceptions import VectorStoreError
from app.core.ports import DocumentRepositoryPort, VectorStorePort

logger = logging.getLogger(__name__)


def create_documents_router(
    doc_repo: DocumentRepositoryPort,
    vector_store: VectorStorePort,
) -> APIRouter:
    router = APIRouter()

    @router.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
    def list_documents():
        """List all ingested documents with their metadata."""
        if doc_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Document management is not available (doc_repo not injected)",
            )
        try:
            docs = doc_repo.list_all()
            return DocumentListResponse(
                total=len(docs),
                documents=[
                    DocumentItem(
                        id=d.id,
                        filename=d.filename,
                        original_filename=getattr(d, "original_filename", d.filename),
                        source_path=d.source_path,
                        file_type=d.file_type,
                        chunk_count=d.chunk_count,
                        ingested_at=d.ingested_at,
                    )
                    for d in docs
                ],
            )
        except Exception as e:
            logger.exception("Failed to list documents")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/documents/{doc_id}", response_model=DocumentItem, tags=["Documents"])
    def get_document(doc_id: str):
        """Get metadata for a single ingested document."""
        if doc_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Document management is not available (doc_repo not injected)",
            )
        try:
            doc = doc_repo.get(doc_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="Document not found")
            return DocumentItem(
                id=doc.id,
                filename=doc.filename,
                original_filename=getattr(doc, "original_filename", doc.filename),
                source_path=doc.source_path,
                file_type=doc.file_type,
                chunk_count=doc.chunk_count,
                ingested_at=doc.ingested_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to get document")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete(
        "/documents/{doc_id}", response_model=DocumentDeleteResponse, tags=["Documents"]
    )
    def delete_document(doc_id: str):
        """
        Delete an ingested document and all its chunks from the vector store.
        """
        if doc_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Document management is not available (doc_repo not injected)",
            )
        try:
            # Get document metadata first
            doc = doc_repo.get(doc_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="Document not found")

            # Delete chunks from vector store by original_filename metadata
            # (Loaders store "source"=path.name, not the full temp path)
            chunks_removed = vector_store.delete_by_metadata(
                "original_filename", doc.original_filename
            )

            # Delete document metadata
            doc_repo.delete(doc_id)

            return DocumentDeleteResponse(
                status="success",
                deleted=True,
                chunks_removed=chunks_removed,
            )
        except HTTPException:
            raise
        except VectorStoreError as e:
            logger.exception("Failed to delete document chunks")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Failed to delete document")
            raise HTTPException(status_code=500, detail=str(e))

    return router
