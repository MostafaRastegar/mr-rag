"""
FastAPI application for the RAG system.

Provides two endpoints:
  - POST /ingest: Ingest a JSON file into the vector store
  - POST /chat: Ask a question and get an answer using RAG
  - GET  /health: Health check
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.document_loader import DocumentLoader
from app.text_splitter import create_text_splitter
from app.embedding_service import EmbeddingService
from app.llm_service import LLMService
from app.vector_store import VectorStore
from app.ingestion_pipeline import IngestionPipeline
from app.rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
embedding_service = EmbeddingService()
llm_service = LLMService()
vector_store = VectorStore()
document_loader = DocumentLoader()

# Initialize pipelines
ingestion_pipeline = IngestionPipeline(
    loader=document_loader,
    embedding_service=embedding_service,
    vector_store=vector_store,
)
rag_pipeline = RAGPipeline(
    embedding_service=embedding_service,
    llm_service=llm_service,
    vector_store=vector_store,
)

app = FastAPI(title="AI RAG System", version="1.0.0")


# --- Request/Response Models ---

class IngestRequest(BaseModel):
    file_path: str


class IngestResponse(BaseModel):
    status: str
    chunks_ingested: int


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    content: str
    metadata: dict
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class HealthResponse(BaseModel):
    status: str
    vector_store_count: int


# --- API Endpoints ---

@app.get("/health", response_model=HealthResponse)
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


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest):
    """
    Ingest a JSON file into the vector store.

    The JSON file should contain a list of objects with
    a 'content' or 'text' field.
    """
    try:
        chunks = ingestion_pipeline.run(request.file_path)
        return IngestResponse(
            status="success",
            chunks_ingested=chunks,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Ask a question and get an answer based on ingested documents.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = rag_pipeline.answer(request.question)
        return ChatResponse(
            answer=result["answer"],
            sources=[SourceItem(**s) for s in result["sources"]],
        )
    except Exception as e:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")