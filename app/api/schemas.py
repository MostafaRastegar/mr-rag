"""
Pydantic request/response schemas for the RAG API.

These define the API contract between the HTTP layer and clients.
"""

from pydantic import BaseModel


class IngestRequest(BaseModel):
    """Request body for the /ingest endpoint."""

    file_path: str


class IngestResponse(BaseModel):
    """Response body for the /ingest endpoint."""

    status: str
    chunks_ingested: int


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    question: str


class SourceItem(BaseModel):
    """A single source document referenced in a chat response."""

    content: str
    metadata: dict
    score: float


class ChatResponse(BaseModel):
    """Response body for the /chat endpoint."""

    answer: str
    sources: list[SourceItem]


class SearchRequest(BaseModel):
    """Request body for the /search endpoint."""

    query: str
    top_k: int = 10


class SearchResultItem(BaseModel):
    """A single result from a vector search."""

    content: str
    metadata: dict
    score: float


class SearchResponse(BaseModel):
    """Response body for the /search endpoint."""

    query: str
    total: int
    results: list[SearchResultItem]


class UploadResponse(BaseModel):
    """Response body for the /upload endpoint."""

    status: str
    file_name: str
    chunks_ingested: int
    message: str


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str
    vector_store_count: int


# ---------------------------------------------------------------------------
# Document Management
# ---------------------------------------------------------------------------


class DocumentItem(BaseModel):
    """A single document metadata record."""

    id: str
    filename: str
    source_path: str
    file_type: str
    chunk_count: int
    ingested_at: float


class DocumentListResponse(BaseModel):
    """Response body for GET /documents."""

    total: int
    documents: list[DocumentItem]


class DocumentDeleteResponse(BaseModel):
    """Response body for DELETE /documents/{id}."""

    status: str
    deleted: bool
    chunks_removed: int


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class SchedulerStatusResponse(BaseModel):
    """Response body for GET /admin/scheduler/status."""

    last_fetch: str | None = None
    total_documents: int | None = None
    status: str | None = None
    error_message: str | None = None


class SchedulerRunResponse(BaseModel):
    """Response body for POST /admin/scheduler/run."""

    status: str
    message: str


class CacheClearResponse(BaseModel):
    """Response body for POST /admin/cache/clear."""

    status: str
    message: str


class AdminStatsResponse(BaseModel):
    """Response body for GET /admin/stats."""

    vector_store_count: int
    document_count: int
    cache_embedding_size: int
    cache_llm_size: int
    cache_rag_size: int


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class ConversationMessageItem(BaseModel):
    """A single message in a conversation."""

    role: str
    content: str
    timestamp: float


class ConversationItem(BaseModel):
    """A single conversation record."""

    id: str
    title: str
    messages: list[ConversationMessageItem]
    created_at: float
    updated_at: float


class ConversationListResponse(BaseModel):
    """Response body for GET /conversations."""

    total: int
    conversations: list[ConversationItem]


class ConversationCreateRequest(BaseModel):
    """Request body for POST /conversations."""

    title: str = "New Conversation"
    messages: list[ConversationMessageItem] = []


class ConversationUpdateRequest(BaseModel):
    """Request body for PUT /conversations/{id}."""

    title: str | None = None
    messages: list[ConversationMessageItem] | None = None


class ConversationDeleteResponse(BaseModel):
    """Response body for DELETE /conversations/{id}."""

    status: str
    deleted: bool
