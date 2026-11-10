"""
Search routes: /search, /admin/retrieval/debug.

Thin layer — delegates to embedding port, vector store, and RAG pipeline.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RetrievalDebugStage,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.config import settings
from app.core.exceptions import EmbeddingError
from app.core.ports import EmbeddingPort, VectorStorePort
from app.pipeline.rag import RAGPipeline

logger = logging.getLogger(__name__)


def create_search_router(
    embedding: EmbeddingPort | None,
    vector_store: VectorStorePort,
    rag: RAGPipeline,
) -> APIRouter:
    router = APIRouter()

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
            dense = vector_store.search(query_embedding, settings.fetch_k)
        except EmbeddingError as e:
            logger.exception("Debug embedding failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Debug retrieval failed")
            raise HTTPException(status_code=500, detail=f"Debug failed: {e}")

        hybrid_stage = None
        reranked_stage = None

        if rag._retriever is not None and settings.hybrid_search_enabled:
            try:
                hybrid_results = rag._retriever.search(
                    query=request.query,
                    query_embedding=query_embedding,
                    top_k=settings.fetch_k,
                    fetch_k=settings.fetch_k,
                )
                hybrid_stage = RetrievalDebugStage(
                    stage="hybrid", count=len(hybrid_results), results=_items(hybrid_results)
                )
            except Exception as e:
                logger.warning("Debug hybrid stage failed: %s", str(e))

        if rag._reranker is not None and settings.rerank_enabled:
            candidates = (
                [r for r in dense] if hybrid_stage is None else hybrid_results
            )
            try:
                reranked = rag._rerank(request.query, candidates)
                reranked_stage = RetrievalDebugStage(
                    stage="reranked",
                    count=len(reranked),
                    results=_items(reranked),
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
            min_score=settings.retrieval_min_score,
            low_relevance_threshold=settings.low_relevance_threshold,
            rerank_min_score=settings.rerank_min_score,
        )

    return router
