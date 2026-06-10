"""
FastAPI application for the RAG system.

Entry point that wires up all dependencies using a manual
dependency injection pattern at module level.
"""

import logging

from fastapi import FastAPI

from app.api.routes import create_router
from app.infrastructure.chroma_vector_store import ChromaVectorStore
from app.infrastructure.document_loader import JsonDocumentLoader
from app.infrastructure.openrouter_embedding import OpenRouterEmbedding
from app.infrastructure.openrouter_llm import OpenRouterLLM
from app.infrastructure.text_splitter import LangChainTextSplitter
from app.pipeline.ingestion import IngestionPipeline
from app.pipeline.rag import RAGPipeline

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Dependency Injection Wiring
# ---------------------------------------------------------------------------

# Infrastructure adapters
embedding = OpenRouterEmbedding()
llm = OpenRouterLLM()
vector_store = ChromaVectorStore()
document_loader = JsonDocumentLoader()
text_splitter = LangChainTextSplitter()

# Application pipelines
ingestion_pipeline = IngestionPipeline(
    loader=document_loader,
    splitter=text_splitter,
    embedding=embedding,
    vector_store=vector_store,
)
rag_pipeline = RAGPipeline(
    embedding=embedding,
    llm=llm,
    vector_store=vector_store,
)

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="AI RAG System", version="1.0.0")

# Register routes with injected dependencies
app.include_router(
    create_router(
        ingestion=ingestion_pipeline,
        rag=rag_pipeline,
        vector_store=vector_store,
    )
)
