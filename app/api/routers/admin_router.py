"""
Admin routes: /admin/scheduler/*, /admin/cache/clear, /admin/stats, /admin/chunks.

Thin layer — delegates to cache adapters, vector store, repositories, scheduler.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AdminStatsResponse,
    CacheClearResponse,
    ChunkDeleteResponse,
    ChunkItem,
    ChunkListResponse,
    SchedulerRunResponse,
    SchedulerStatusResponse,
)
from app.core.exceptions import VectorStoreError
from app.core.ports import (
    CachePort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    VectorStorePort,
)
from app.scheduler.job import run_with_retry
from app.scheduler.logger import read_last_fetch

logger = logging.getLogger(__name__)


def create_admin_router(
    vector_store: VectorStorePort,
    doc_repo: DocumentRepositoryPort | None = None,
    conversation_repo: ConversationRepositoryPort | None = None,
    cache_embedding: CachePort | None = None,
    cache_llm: CachePort | None = None,
    cache_rag: CachePort | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/admin/scheduler/run", response_model=SchedulerRunResponse, tags=["Admin"]
    )
    def admin_scheduler_run():
        """
        Manually trigger the scheduler job.
        Fetches data from the Scraper API, ingests it, and cleans up.
        """
        try:
            run_with_retry()
            return SchedulerRunResponse(
                status="success",
                message="Scheduler job completed successfully",
            )
        except Exception as e:
            logger.exception("Manual scheduler run failed")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        "/admin/scheduler/status",
        response_model=SchedulerStatusResponse,
        tags=["Admin"],
    )
    def admin_scheduler_status():
        """Get the status of the last scheduler fetch."""
        try:
            log = read_last_fetch()
            if log is None:
                return SchedulerStatusResponse()
            return SchedulerStatusResponse(
                last_fetch=log.get("last_fetch"),
                total_documents=log.get("total_documents"),
                status=log.get("status"),
                error_message=log.get("error_message"),
            )
        except Exception as e:
            logger.exception("Failed to read scheduler status")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post(
        "/admin/cache/clear", response_model=CacheClearResponse, tags=["Admin"]
    )
    def admin_cache_clear():
        """Clear all cache layers (embedding, LLM, and RAG)."""
        cleared = []
        if cache_embedding is not None:
            try:
                cache_embedding.clear()
                cleared.append("embedding")
            except Exception as e:
                logger.warning("Failed to clear embedding cache: %s", e)
        if cache_llm is not None:
            try:
                cache_llm.clear()
                cleared.append("llm")
            except Exception as e:
                logger.warning("Failed to clear LLM cache: %s", e)
        if cache_rag is not None:
            try:
                cache_rag.clear()
                cleared.append("rag")
            except Exception as e:
                logger.warning("Failed to clear RAG cache: %s", e)

        return CacheClearResponse(
            status="success",
            message=f"Cache cleared: {', '.join(cleared) if cleared else 'none'}",
        )

    @router.get("/admin/stats", response_model=AdminStatsResponse, tags=["Admin"])
    def admin_stats():
        """Get overall system statistics."""
        try:
            vector_count = vector_store.count()
        except Exception:
            vector_count = -1

        doc_count = doc_repo.count() if doc_repo is not None else -1

        cache_embedding_size = cache_embedding.size() if cache_embedding is not None else -1
        cache_llm_size = cache_llm.size() if cache_llm is not None else -1
        cache_rag_size = cache_rag.size() if cache_rag is not None else -1

        return AdminStatsResponse(
            vector_store_count=vector_count,
            document_count=doc_count,
            cache_embedding_size=cache_embedding_size,
            cache_llm_size=cache_llm_size,
            cache_rag_size=cache_rag_size,
        )

    @router.get("/admin/chunks", response_model=ChunkListResponse, tags=["Admin"])
    def admin_list_chunks():
        """
        List all chunks in the vector store with their metadata.
        Useful for debugging and manual inspection.
        """
        try:
            chunks = vector_store.get_all_chunks()
            return ChunkListResponse(
                total=len(chunks),
                chunks=[
                    ChunkItem(id=c.id, text=c.text[:200], metadata=c.metadata)
                    for c in chunks
                ],
            )
        except VectorStoreError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Failed to list chunks")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete(
        "/admin/chunks/{chunk_id}",
        response_model=ChunkDeleteResponse,
        tags=["Admin"],
    )
    def admin_delete_chunk(chunk_id: str):
        """Delete a single chunk from the vector store by its ID."""
        try:
            vector_store.delete([chunk_id])
            return ChunkDeleteResponse(status="success", deleted=True)
        except VectorStoreError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Failed to delete chunk")
            raise HTTPException(status_code=500, detail=str(e))

    return router
