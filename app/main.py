"""
FastAPI application for the RAG system.

Entry point that wires up all dependencies using a manual
dependency injection pattern at module level.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import create_router
from app.core.ports import CachePort
from app.infrastructure.cache import (
    InMemoryCacheAdapter,
    SemanticCacheAdapter,
    SQLiteCacheAdapter,
)
from app.infrastructure.chroma_vector_store import ChromaVectorStore
from app.infrastructure.document_loader import AutoDocumentLoader
from app.infrastructure.openrouter_embedding import OpenRouterEmbedding
from app.infrastructure.openrouter_llm import OpenRouterLLM
from app.infrastructure.text_splitter import LangChainTextSplitter
from app.pipeline.ingestion import IngestionPipeline
from app.pipeline.rag import RAGPipeline

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Dependency Injection Wiring
# ---------------------------------------------------------------------------

# Cache adapters
_cache_embedding: CachePort
_cache_llm: CachePort
_cache_rag: CachePort

if settings.cache_type == "sqlite":
    _cache_embedding = SQLiteCacheAdapter(ttl_seconds=settings.cache_ttl_embedding)
    _cache_llm = SQLiteCacheAdapter(ttl_seconds=settings.cache_ttl_llm)
    logging.getLogger(__name__).info("Using SQLite cache (persistent)")
else:
    _cache_embedding = InMemoryCacheAdapter(maxsize=settings.cache_maxsize)
    _cache_llm = InMemoryCacheAdapter(maxsize=settings.cache_maxsize)
    logging.getLogger(__name__).info("Using InMemory cache (ephemeral)")

# RAG pipeline uses SemanticCacheAdapter (hybrid exact + semantic)
_cache_rag = SemanticCacheAdapter(
    maxsize=settings.cache_semantic_maxsize,
    default_threshold=settings.cache_semantic_threshold,
)
logging.getLogger(__name__).info(
    "Using Semantic cache for RAG (maxsize=%d, threshold=%.2f)",
    settings.cache_semantic_maxsize,
    settings.cache_semantic_threshold,
)

# Infrastructure adapters
embedding = OpenRouterEmbedding(cache=_cache_embedding)
llm = OpenRouterLLM(cache=_cache_llm)
vector_store = ChromaVectorStore()
document_loader = AutoDocumentLoader()
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
    cache=_cache_rag,
)

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(title="AI RAG System", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS — allow frontend dev server
# ---------------------------------------------------------------------------

_ALLOWED_ORIGINS = getattr(settings, "cors_origins", None)
if _ALLOWED_ORIGINS:
    origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]
else:
    # default: localhost:3000 (Next.js dev) + production port 8080
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes with injected dependencies
app.include_router(
    create_router(
        ingestion=ingestion_pipeline,
        rag=rag_pipeline,
        vector_store=vector_store,
        embedding=embedding,
    )
)
