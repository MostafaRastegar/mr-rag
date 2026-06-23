"""
FastAPI route handlers for the RAG API.

Thin layer: each handler validates the request, calls the appropriate
pipeline, and returns a serialized response. No business logic here.
"""

import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    AdminStatsResponse,
    CacheClearResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
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
    SchedulerRunResponse,
    SchedulerStatusResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceItem,
    UploadResponse,
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
from app.pipeline.rag import RAGPipeline
from app.scheduler.logger import read_last_fetch
from app.scheduler.job import run_with_retry

logger = logging.getLogger(__name__)


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

    @router.get("/health", response_model=HealthResponse)
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

    @router.post("/ingest", response_model=IngestResponse)
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

    @router.post("/chat", response_model=ChatResponse)
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

    @router.post("/chat/stream")
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
            media_type="text/plain",
        )

    @router.post("/search", response_model=SearchResponse)
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

    @router.post("/upload", response_model=UploadResponse)
    async def upload_file(file: UploadFile = File(...)):
        """
        Upload a file (JSON, MD, or TXT) and ingest it into the vector store.

        The file is saved to a temporary location, ingested, then deleted.
        """
        # validate extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".json", ".md", ".txt", ".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Use .json, .md, or .txt",
            )

        # save to temp file
        tmp = tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, mode="wb"
        )
        try:
            content = await file.read()
            tmp.write(content)
            tmp.close()

            chunks = ingestion.run(tmp.name, original_filename=file.filename or "unknown")
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

    @router.get("/documents", response_model=DocumentListResponse)
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

    @router.get("/documents/{doc_id}", response_model=DocumentItem)
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

    @router.delete("/documents/{doc_id}", response_model=DocumentDeleteResponse)
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

            # Delete chunks from vector store by source_path metadata
            chunks_removed = vector_store.delete_by_metadata(
                "source", doc.source_path
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

    @router.post("/admin/scheduler/run", response_model=SchedulerRunResponse)
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

    @router.get("/admin/scheduler/status", response_model=SchedulerStatusResponse)
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

    @router.post("/admin/cache/clear", response_model=CacheClearResponse)
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

    @router.get("/admin/stats", response_model=AdminStatsResponse)
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

    # ------------------------------------------------------------------
    # Conversation Endpoints
    # ------------------------------------------------------------------

    @router.get("/conversations", response_model=ConversationListResponse)
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

    @router.get("/conversations/{conv_id}", response_model=ConversationItem)
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

    @router.post("/conversations", response_model=ConversationItem, status_code=201)
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

    @router.put("/conversations/{conv_id}", response_model=ConversationItem)
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

    @router.delete("/conversations/{conv_id}", response_model=ConversationDeleteResponse)
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

    @router.get("/metrics")
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
