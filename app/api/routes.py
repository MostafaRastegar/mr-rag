"""
FastAPI route handlers for the RAG API.

Thin aggregation layer: each handler lives in a dedicated router under
``app/api/routers/``.  This file only wires them together through
``create_router()`` so the public DI factory stays backward-compatible.
"""

import logging

from fastapi import APIRouter

from app.api.routers.admin_router import create_admin_router
from app.api.routers.chat_router import create_chat_router
from app.api.routers.upload_router import create_upload_router
from app.api.routers.confluence_router import create_confluence_router
from app.api.routers.conversations_router import create_conversations_router
from app.api.routers.documents_router import create_documents_router
from app.api.routers.ingestion_router import create_ingestion_router
from app.api.routers.search_router import create_search_router
from app.api.routers.system_router import create_system_router

logger = logging.getLogger(__name__)


def create_router(
    ingestion,
    rag,
    vector_store,
    embedding=None,
    doc_repo=None,
    conversation_repo=None,
    cache_embedding=None,
    cache_llm=None,
    cache_rag=None,
) -> APIRouter:
    """
    Factory function to create the API router with dependency injection.

    Aggregates all domain routers into a single APIRouter.  Signature and
    behaviour are identical to the previous monolithic implementation.
    """
    router = APIRouter()

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------
    router.include_router(
        create_system_router(vector_store=vector_store),
    )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    router.include_router(
        create_ingestion_router(ingestion=ingestion),
    )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    router.include_router(
        create_upload_router(ingestion=ingestion),
    )

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    router.include_router(
        create_chat_router(rag=rag),
    )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    router.include_router(
        create_search_router(
            embedding=embedding,
            vector_store=vector_store,
            rag=rag,
        ),
    )

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------
    router.include_router(
        create_documents_router(
            doc_repo=doc_repo,
            vector_store=vector_store,
        ),
    )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------
    router.include_router(
        create_conversations_router(
            conversation_repo=conversation_repo,
        ),
    )

    # ------------------------------------------------------------------
    # Confluence
    # ------------------------------------------------------------------
    router.include_router(
        create_confluence_router(
            ingestion=ingestion,
            vector_store=vector_store,
        ),
    )

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    router.include_router(
        create_admin_router(
            vector_store=vector_store,
            doc_repo=doc_repo,
            conversation_repo=conversation_repo,
            cache_embedding=cache_embedding,
            cache_llm=cache_llm,
            cache_rag=cache_rag,
        ),
    )

    return router
