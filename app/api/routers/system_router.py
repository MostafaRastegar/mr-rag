"""
System routes: /health, /metrics.

Thin layer — delegates to injected ports, no business logic.
"""

import logging

from fastapi import APIRouter, HTTPException, Response

from app.api.schemas import HealthResponse
from app.core.ports import VectorStorePort

logger = logging.getLogger(__name__)


def create_system_router(
    vector_store: VectorStorePort,
) -> APIRouter:
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

        metrics_text = f"""# HELP rag_vector_store_count Number of chunks in vector store
# TYPE rag_vector_store_count gauge
rag_vector_store_count {vector_count}
"""
        return Response(content=metrics_text, media_type="text/plain")

    return router
