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
