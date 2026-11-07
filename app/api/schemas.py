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


class ChatMessage(BaseModel):
    """A single message in the chat history."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    question: str
    messages: list[ChatMessage] = []


class SourceItem(BaseModel):
    """A single source document referenced in a chat response."""

    content: str
    metadata: dict
    score: float
    # Human-readable origin (original filename, plus page/section when known).
    source_name: str | None = None
    chunk_id: str | None = None


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


class RetrievalDebugRequest(BaseModel):
    """Request body for the /admin/retrieval/debug endpoint."""

    query: str
    top_k: int | None = None


class RetrievalDebugStage(BaseModel):
    """Results produced by one retrieval stage."""

    stage: str
    count: int
    results: list[SearchResultItem]


class RetrievalDebugResponse(BaseModel):
    """
    Full retrieval trace for a single query.

    Exposes every stage of the retrieval pipeline side by side so a poor
    answer can be traced to a specific stage: dense recall, hybrid fusion or
    reranking. Without this, "the answer was wrong" is not attributable.
    """

    query: str
    dense: RetrievalDebugStage
    hybrid: RetrievalDebugStage | None = None
    reranked: RetrievalDebugStage | None = None
    # Decision inputs the pipeline itself uses.
    min_score: float
    low_relevance_threshold: float
    rerank_min_score: float


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
    original_filename: str
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


class ChunkItem(BaseModel):
    """A single chunk in the vector store."""

    id: str
    text: str
    metadata: dict


class ChunkListResponse(BaseModel):
    """Response body for GET /admin/chunks."""

    total: int
    chunks: list[ChunkItem]


class ChunkDeleteResponse(BaseModel):
    """Response body for DELETE /admin/chunks/{chunk_id}."""

    status: str
    deleted: bool


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class ConversationMessageItem(BaseModel):
    """A single message in a conversation."""

    role: str
    content: str
    timestamp: float | None = None


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


# ---------------------------------------------------------------------------
# Confluence
# ---------------------------------------------------------------------------

class ConfluenceCreds(BaseModel):
    """User-supplied Confluence credentials (session-only, never stored)."""

    base_url: str
    auth_type: str = "bearer"  # "bearer" or "basic"
    token: str
    email: str | None = None
    username: str | None = None


class ConfluenceTestRequest(ConfluenceCreds):
    pass


class ConfluenceTestResponse(BaseModel):
    ok: bool
    user: str | None = None
    spaces_count: int | None = None


class ConfluenceSpacesRequest(ConfluenceCreds):
    limit: int = 100


class ConfluenceSpaceItem(BaseModel):
    key: str
    name: str


class ConfluenceSpacesResponse(BaseModel):
    spaces: list[ConfluenceSpaceItem]


class ConfluencePagesRequest(ConfluenceCreds):
    space_key: str | None = None
    parent_page_id: str | None = None
    start: int = 0
    limit: int = 100


class ConfluencePageItem(BaseModel):
    id: str
    title: str
    space_key: str
    url: str
    version: str | None = None


class ConfluencePagesResponse(BaseModel):
    pages: list[ConfluencePageItem]
    has_more: bool


class ConfluenceIndexRequest(ConfluenceCreds):
    mode: str  # "ids" | "space" | "subtree"
    page_ids: list[str] | None = None
    space_key: str | None = None
    root_page_id: str | None = None
    recursive: bool = False


class ConfluenceIndexResponse(BaseModel):
    status: str
    pages_indexed: int
    pages_failed: int
    chunks_ingested: int
    errors: list[dict] = []


class ConfluenceSyncRequest(ConfluenceIndexRequest):
    pass


class ConfluenceSyncResponse(ConfluenceIndexResponse):
    pass


class ConfluenceStatusResponse(BaseModel):
    last_sync: float | None = None
    duration_seconds: float | None = None
    pages_indexed: int | None = None
    pages_failed: int | None = None
    chunks_ingested: int | None = None
    error: str | None = None
