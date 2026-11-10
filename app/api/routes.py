"""
FastAPI route handlers for the RAG API.

Thin layer: each handler validates the request, calls the appropriate
pipeline, and returns a serialized response. No business logic here.
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AdminStatsResponse,
    CacheClearResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChunkDeleteResponse,
    ChunkItem,
    ChunkListResponse,
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationItem,
    ConversationListResponse,
    ConversationMessageItem,
    ConversationUpdateRequest,
    DocumentDeleteResponse,
    DocumentItem,
    DocumentListResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RetrievalDebugStage,
    SchedulerRunResponse,
    SchedulerStatusResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceItem,
    UploadResponse,
    ConfluenceTestRequest,
    ConfluenceTestResponse,
    ConfluenceSpacesRequest,
    ConfluenceSpacesResponse,
    ConfluencePagesRequest,
    ConfluencePagesResponse,
    ConfluenceIndexRequest,
    ConfluenceIndexResponse,
    ConfluenceSyncRequest,
    ConfluenceSyncResponse,
    ConfluenceStatusResponse,
    ConfluenceSpaceItem,
    ConfluencePageItem,
)
from app.core.domain import Conversation, ConversationMessage
from app.core.exceptions import (
    DocumentLoadError,
    EmbeddingError,
    IngestionError,
    RetrievalError,
    VectorStoreError,
)
from app.core.ports import (
    CachePort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    EmbeddingPort,
    VectorStorePort,
)
from app.pipeline.ingestion import IngestionPipeline
from app.pipeline.confluence_ingestion import ConfluenceIngestionService
from app.pipeline.rag import RAGPipeline
from app.scheduler.logger import read_last_fetch
from app.scheduler.job import run_with_retry
from app.infrastructure.confluence_client import ConfluenceClient, ConfluenceError
from app.config import settings

logger = logging.getLogger(__name__)


def _source_label(metadata: dict | None) -> str | None:
    """
    Build a human-readable source label from chunk metadata.

    Prefers `original_filename` because chunks ingested from temp files carry a
    meaningless `source` such as `/tmp/tmpab12cd.txt`. Page and section are
    appended when present so a citation can be located in the source document.

    Args:
        metadata: Chunk metadata.

    Returns:
        A label string, or None when no usable filename is present.
    """
    if not metadata:
        return None

    name = metadata.get("original_filename") or metadata.get("source")
    if not name:
        return None

    label = str(name).split("/")[-1]
    if metadata.get("page") is not None:
        label = f"{label}, p.{metadata['page']}"
    elif metadata.get("section"):
        label = f"{label} — {metadata['section']}"
    return label


# ---------------------------------------------------------------------------
# Confluence helpers
# ---------------------------------------------------------------------------

_CONFLUENCE_LOG_PATH = Path("data/confluence_sync_log.json")


def _check_allowed_host(base_url: str) -> None:
    """Reject Confluence hosts not in CONFLUENCE_ALLOWED_HOSTS (SSRF guard)."""
    allowed = settings.confluence_allowed_hosts
    if not allowed:
        return
    host = (urlparse(base_url).hostname or "").lower()
    hosts = {h.strip().lower() for h in allowed.split(",") if h.strip()}
    if host not in hosts:
        raise HTTPException(
            status_code=400, detail=f"Confluence host not allowed: {host}"
        )


def _make_client(request) -> ConfluenceClient:
    return ConfluenceClient(
        request.base_url,
        auth_type=request.auth_type,
        token=request.token,
        email=request.email,
        username=request.username,
        timeout=settings.confluence_timeout_seconds,
    )


def _index_with_client(request, client: ConfluenceClient) -> ConfluenceIndexResponse:
    service = ConfluenceIngestionService(
        ingestion, vector_store, max_pages=settings.confluence_max_pages
    )
    result = service.index(
        client=client,
        mode=request.mode,
        page_ids=request.page_ids,
        space_key=request.space_key,
        root_page_id=request.root_page_id,
        recursive=request.recursive,
    )
    return ConfluenceIndexResponse(
        status="success",
        pages_indexed=result.pages_indexed,
        pages_failed=result.pages_failed,
        chunks_ingested=result.chunks_ingested,
        errors=result.errors,
    )


def create_router(
    ingestion: IngestionPipeline,
    rag: RAGPipeline,
    vector_store: VectorStorePort,
    embedding: EmbeddingPort | None = None,
    doc_repo: DocumentRepositoryPort | None = None,
    conversation_repo: ConversationRepositoryPort | None = None,
    cache_embedding: CachePort | None = None,
    cache_llm: CachePort | None = None,
    cache_rag: CachePort | None = None,
) -> APIRouter:
    """
    Factory function to create the API router with dependency injection.

    Args:
        ingestion: The ingestion pipeline instance.
        rag: The RAG pipeline instance.
        vector_store: The vector store instance.
        embedding: Optional embedding port for the search endpoint.
        doc_repo: Optional document repository for document management.
        conversation_repo: Optional conversation repository for chat history.
        cache_embedding: Optional embedding cache for admin stats.
        cache_llm: Optional LLM cache for admin stats.
        cache_rag: Optional RAG cache for admin stats.

    Returns:
        A configured APIRouter with all endpoints.
    """
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["System"])
    def health():
        """Health check endpoint."""
        try:
            count = vector_store.count()
        except Exception:
            count = -1

        return HealthResponse(
            status="ok" if count >= 0 else "degraded",
            vector_store_count=count,
        )

    @router.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
    def ingest(request: IngestRequest):
        """
        Ingest a JSON file into the vector store.
        """
        try:
            chunks = ingestion.run(request.file_path)
            return IngestResponse(
                status="success",
                chunks_ingested=chunks,
            )
        except (FileNotFoundError, DocumentLoadError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except IngestionError as e:
            logger.exception("Ingestion failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected ingestion error")
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    # ------------------------------------------------------------------
    # Confluence endpoints
    # ------------------------------------------------------------------

    @router.post(
        "/confluence/test", response_model=ConfluenceTestResponse, tags=["Confluence"]
    )
    def confluence_test(request: ConfluenceTestRequest):
        """Validate Confluence URL + credentials."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                info = client.test_connection()
                spaces = client.list_spaces(limit=1)
            return ConfluenceTestResponse(
                ok=True,
                user=str(info.get("displayName") or info.get("username") or ""),
                spaces_count=len(spaces),
            )
        except ConfluenceError as e:
            logger.exception("Confluence test connection failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/spaces",
        response_model=ConfluenceSpacesResponse,
        tags=["Confluence"],
    )
    def confluence_spaces(request: ConfluenceSpacesRequest):
        """List accessible Confluence spaces."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                spaces = client.list_spaces(limit=request.limit)
            return ConfluenceSpacesResponse(
                spaces=[
                    ConfluenceSpaceItem(
                        key=str(s.get("key", "")), name=str(s.get("name", ""))
                    )
                    for s in spaces
                ]
            )
        except ConfluenceError as e:
            logger.exception("Confluence list spaces failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/pages",
        response_model=ConfluencePagesResponse,
        tags=["Confluence"],
    )
    def confluence_pages(request: ConfluencePagesRequest):
        """List Confluence pages in a space or under a parent page."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                data = client.list_pages(
                    space_key=request.space_key,
                    parent_page_id=request.parent_page_id,
                    start=request.start,
                    limit=request.limit,
                )
            base = request.base_url.rstrip("/")
            pages = []
            for p in data.get("results", []):
                pid = str(p.get("id", ""))
                pages.append(
                    ConfluencePageItem(
                        id=pid,
                        title=str(p.get("title", "")),
                        space_key=str((p.get("space") or {}).get("key", "")),
                        url=f"{base}/pages/viewpage.action?pageId={pid}",
                        version=str((p.get("version") or {}).get("number", "")) or None,
                    )
                )
            return ConfluencePagesResponse(
                pages=pages,
                has_more=bool(data.get("_links", {}).get("next")),
            )
        except ConfluenceError as e:
            logger.exception("Confluence list pages failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/index",
        response_model=ConfluenceIndexResponse,
        tags=["Confluence"],
    )
    def confluence_index(request: ConfluenceIndexRequest):
        """Index Confluence pages (ids / space / subtree). Idempotent per page."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                result = _index_with_client(request, client)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ConfluenceError as e:
            logger.exception("Confluence index failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/sync",
        response_model=ConfluenceSyncResponse,
        tags=["Confluence"],
    )
    def confluence_sync(request: ConfluenceSyncRequest):
        """Re-index Confluence pages (same body as /index)."""
        return confluence_index(request)

    @router.get(
        "/confluence/status", response_model=ConfluenceStatusResponse, tags=["Confluence"]
    )
    def confluence_status():
        """Last Confluence sync status."""
        if not _CONFLUENCE_LOG_PATH.exists():
            return ConfluenceStatusResponse()
        try:
            entry = json.loads(_CONFLUENCE_LOG_PATH.read_text(encoding="utf-8"))
            return ConfluenceStatusResponse(
                last_sync=entry.get("last_sync"),
                duration_seconds=entry.get("duration_seconds"),
                pages_indexed=entry.get("pages_indexed"),
                pages_failed=entry.get("pages_failed"),
                chunks_ingested=entry.get("chunks_ingested"),
                error=entry.get("error"),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read Confluence sync log: %s", e)
            return ConfluenceStatusResponse()

    @router.post("/chat", response_model=ChatResponse, tags=["Chat"])
    def chat(request: ChatRequest):
        """
        Ask a question and get an answer based on ingested documents.
        """
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Convert ChatMessage objects to dicts for the pipeline
        history = [{"role": m.role, "content": m.content} for m in request.messages]

        try:
            answer = rag.answer(request.question, history)
            return ChatResponse(
                answer=answer.text,
                sources=[
                    SourceItem(
                        content=s.chunk.text[:200],
                        metadata=s.chunk.metadata,
                        score=s.score,
                        source_name=_source_label(s.chunk.metadata),
                        chunk_id=s.chunk.id or None,
                    )
                    for s in answer.sources
                ],
            )
        except RetrievalError as e:
            logger.exception("Chat failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected chat error")
            raise HTTPException(status_code=500, detail=f"Chat failed: {e}")

    @router.post("/chat/stream", tags=["Chat"])
    async def chat_stream(request: ChatRequest):
        """
        Ask a question and get a streaming answer based on ingested documents.

        Uses SSE (Server-Sent Events) to stream tokens progressively.
        The client receives tokens one by one as they are generated by the LLM,
        allowing for real-time display instead of waiting for the full response.
        """
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        # Convert ChatMessage objects to dicts for the pipeline
        history = [{"role": m.role, "content": m.content} for m in request.messages]

        return StreamingResponse(
            rag.answer_stream(request.question, history),
            media_type="text/event-stream",
        )

    @router.post("/search", response_model=SearchResponse, tags=["Search"])
    def search(request: SearchRequest):
        """
        Direct vector search — no LLM call.

        Embeds the query, searches ChromaDB, and returns raw matching
        chunks with their relevance scores and metadata.
        """
        if embedding is None:
            raise HTTPException(
                status_code=501,
                detail="Search endpoint is not available (embedding port not injected)",
            )

        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        try:
            query_embedding = embedding.embed_query(request.query)
            results = vector_store.search(query_embedding, request.top_k)
        except EmbeddingError as e:
            logger.exception("Search embedding failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected search error")
            raise HTTPException(status_code=500, detail=f"Search failed: {e}")

        return SearchResponse(
            query=request.query,
            total=len(results),
            results=[
                SearchResultItem(
                    content=r.chunk.text[:500],
                    metadata=r.chunk.metadata,
                    score=r.score,
                )
                for r in results
            ],
        )

    @router.post(
        "/admin/retrieval/debug",
        response_model=RetrievalDebugResponse,
        tags=["Admin"],
    )
    def retrieval_debug(request: RetrievalDebugRequest):
        """
        Trace every retrieval stage for one query without calling the LLM.

        Runs dense search, hybrid fusion and reranking independently and
        returns each stage's ranked output along with the thresholds the
        pipeline uses to make decisions. This makes a bad answer attributable
        to a specific stage instead of a black box.
        """
        if embedding is None:
            raise HTTPException(
                status_code=501,
                detail="Debug endpoint requires the embedding port",
            )

        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        from app.config import settings as _settings

        def _items(results) -> list[SearchResultItem]:
            return [
                SearchResultItem(
                    content=r.chunk.text[:500],
                    metadata=r.chunk.metadata,
                    score=r.score,
                )
                for r in results
            ]

        try:
            query_embedding = embedding.embed_query(request.query)
            dense = vector_store.search(query_embedding, _settings.fetch_k)
        except EmbeddingError as e:
            logger.exception("Debug embedding failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Debug retrieval failed")
            raise HTTPException(status_code=500, detail=f"Debug failed: {e}")

        hybrid_stage = None
        reranked_stage = None

        if rag._retriever is not None and _settings.hybrid_search_enabled:
            try:
                hybrid_results = rag._retriever.search(
                    query=request.query,
                    query_embedding=query_embedding,
                    top_k=_settings.fetch_k,
                    fetch_k=_settings.fetch_k,
                )
                hybrid_stage = RetrievalDebugStage(
                    stage="hybrid", count=len(hybrid_results), results=_items(hybrid_results)
                )
            except Exception as e:
                logger.warning("Debug hybrid stage failed: %s", str(e))

        if rag._reranker is not None and _settings.rerank_enabled:
            candidates = (
                [r for r in dense] if hybrid_stage is None else hybrid_results
            )
            try:
                reranked = rag._rerank(request.query, candidates)
                reranked_stage = RetrievalDebugStage(
                    stage="reranked", count=len(reranked), results=_items(reranked)
                )
            except Exception as e:
                logger.warning("Debug rerank stage failed: %s", str(e))

        return RetrievalDebugResponse(
            query=request.query,
            dense=RetrievalDebugStage(
                stage="dense", count=len(dense), results=_items(dense)
            ),
            hybrid=hybrid_stage,
            reranked=reranked_stage,
            min_score=_settings.retrieval_min_score,
            low_relevance_threshold=_settings.retrieval_low_relevance_threshold,
            rerank_min_score=_settings.rerank_min_score,
        )

    @router.post("/upload", response_model=UploadResponse, tags=["Ingestion"])
    async def upload_file(
        file: UploadFile = File(..., json_schema_extra={"format": "binary"}),
    ):
        """
        Upload a file (JSON, MD, TXT, or PDF) and ingest it into the vector store.

        The file is saved to a temporary location, ingested, then deleted.
        """
        # validate extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".json", ".md", ".txt", ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Use .json, .md, .txt, .pdf, or image files",
            )

        # save to temp file
        tmp = tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, mode="wb"
        )
        try:
            content = await file.read()
            tmp.write(content)
            tmp.close()

            chunks = await asyncio.to_thread(
                ingestion.run, tmp.name, original_filename=file.filename or "unknown"
            )
            return UploadResponse(
                status="success",
                file_name=file.filename or "unknown",
                chunks_ingested=chunks,
                message=f"فایل با موفقیت بارگذاری شد. {chunks} قطعه استخراج شد.",
            )
        except (DocumentLoadError, IngestionError) as e:
            logger.exception("Upload ingestion failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected upload error")
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    # ------------------------------------------------------------------
    # Document Management Endpoints
    # ------------------------------------------------------------------

    @router.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
    def list_documents():
        """
        List all ingested documents with their metadata.
        """
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
        """
        Get metadata for a single ingested document.
        """
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

    # ------------------------------------------------------------------
    # Admin Endpoints
    # ------------------------------------------------------------------

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
        """
        Get the status of the last scheduler fetch.
        """
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
        """
        Clear all cache layers (embedding, LLM, and RAG).
        """
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
        """
        Get overall system statistics.
        """
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
        """
        Delete a single chunk from the vector store by its ID.
        """
        try:
            vector_store.delete([chunk_id])
            return ChunkDeleteResponse(status="success", deleted=True)
        except VectorStoreError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Failed to delete chunk")
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # Conversation Endpoints
    # ------------------------------------------------------------------

    @router.get(
        "/conversations", response_model=ConversationListResponse, tags=["Conversations"]
    )
    def list_conversations(limit: int = 50, offset: int = 0):
        """
        List all conversations, most recent first.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            convos = conversation_repo.list_all(limit=limit, offset=offset)
            total = conversation_repo.count()
            return ConversationListResponse(
                total=total,
                conversations=[
                    ConversationItem(
                        id=c.id,
                        title=c.title,
                        messages=[
                            ConversationMessageItem(
                                role=m.role,
                                content=m.content,
                                timestamp=m.timestamp,
                            )
                            for m in c.messages
                        ],
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                    for c in convos
                ],
            )
        except Exception as e:
            logger.exception("Failed to list conversations")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        "/conversations/{conv_id}", response_model=ConversationItem, tags=["Conversations"]
    )
    def get_conversation(conv_id: str):
        """
        Get a single conversation with all its messages.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            conv = conversation_repo.get(conv_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to get conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post(
        "/conversations",
        response_model=ConversationItem,
        status_code=201,
        tags=["Conversations"],
    )
    def create_conversation(request: ConversationCreateRequest):
        """
        Create a new conversation.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            import time
            import uuid
            now = time.time()
            conv = Conversation(
                id=str(uuid.uuid4()),
                title=request.title,
                messages=[
                    ConversationMessage(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp or now,
                    )
                    for m in request.messages
                ],
                created_at=now,
                updated_at=now,
            )
            conversation_repo.save(conv)
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except Exception as e:
            logger.exception("Failed to create conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        "/conversations/{conv_id}", response_model=ConversationItem, tags=["Conversations"]
    )
    def update_conversation(conv_id: str, request: ConversationUpdateRequest):
        """
        Update a conversation's title and/or messages.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            import time
            conv = conversation_repo.get(conv_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")

            if request.title is not None:
                conv.title = request.title
            if request.messages is not None:
                conv.messages = [
                    ConversationMessage(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in request.messages
                ]
            conv.updated_at = time.time()
            conversation_repo.save(conv)
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to update conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete(
        "/conversations/{conv_id}",
        response_model=ConversationDeleteResponse,
        tags=["Conversations"],
    )
    def delete_conversation(conv_id: str):
        """
        Delete a conversation.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            deleted = conversation_repo.delete(conv_id)
            return ConversationDeleteResponse(
                status="success" if deleted else "not_found",
                deleted=deleted,
            )
        except Exception as e:
            logger.exception("Failed to delete conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/metrics", tags=["System"])
    def metrics():
        """
        Prometheus-style metrics endpoint.

        Returns basic system metrics in text format.
        """
        try:
            vector_count = vector_store.count()
        except Exception:
            vector_count = -1

        doc_count = doc_repo.count() if doc_repo is not None else -1
        conv_count = conversation_repo.count() if conversation_repo is not None else -1

        cache_embedding_size = cache_embedding.size() if cache_embedding is not None else 0
        cache_llm_size = cache_llm.size() if cache_llm is not None else 0
        cache_rag_size = cache_rag.size() if cache_rag is not None else 0

        metrics_text = f"""# HELP rag_vector_store_count Number of chunks in vector store
# TYPE rag_vector_store_count gauge
rag_vector_store_count {vector_count}

# HELP rag_document_count Number of ingested documents
# TYPE rag_document_count gauge
rag_document_count {doc_count}

# HELP rag_conversation_count Number of conversations
# TYPE rag_conversation_count gauge
rag_conversation_count {conv_count}

# HELP rag_cache_embedding_size Number of entries in embedding cache
# TYPE rag_cache_embedding_size gauge
rag_cache_embedding_size {cache_embedding_size}

# HELP rag_cache_llm_size Number of entries in LLM cache
# TYPE rag_cache_llm_size gauge
rag_cache_llm_size {cache_llm_size}

# HELP rag_cache_rag_size Number of entries in RAG cache
# TYPE rag_cache_rag_size gauge
rag_cache_rag_size {cache_rag_size}
"""
        return Response(content=metrics_text, media_type="text/plain")

    return router
