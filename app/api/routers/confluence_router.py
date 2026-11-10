"""
Confluence routes: /confluence/test, /confluence/spaces, /confluence/pages,
/confluence/index, /confluence/sync, /confluence/status.

Thin layer — delegates to ConfluenceClient and ConfluenceIngestionService.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ConfluenceIndexRequest,
    ConfluenceIndexResponse,
    ConfluencePagesRequest,
    ConfluencePagesResponse,
    ConfluencePageItem,
    ConfluenceSpaceItem,
    ConfluenceSpacesRequest,
    ConfluenceSpacesResponse,
    ConfluenceStatusResponse,
    ConfluenceSyncRequest,
    ConfluenceSyncResponse,
    ConfluenceTestRequest,
    ConfluenceTestResponse,
)
from app.infrastructure.confluence_client import ConfluenceError
from app.pipeline.confluence_ingestion import ConfluenceIngestionService
from app.core.ports import VectorStorePort
from app.pipeline.ingestion import IngestionPipeline
from app.api.routers._helpers import (
    _CONFLUENCE_LOG_PATH,
    _check_allowed_host,
    _index_with_client,
    _make_client,
)

logger = logging.getLogger(__name__)


def create_confluence_router(
    ingestion: IngestionPipeline,
    vector_store: VectorStorePort,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/confluence/test", response_model=ConfluenceTestResponse, tags=["Confluence"]
    )
    def confluence_test(request: ConfluenceTestRequest):
        """Validate Confluence URL + credentials."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                info = client.test_connection()
                spaces = client.list_spaces(limit=1)
            return ConfluenceTestResponse(
                ok=True,
                user=str(info.get("displayName") or info.get("username") or ""),
                spaces_count=len(spaces),
            )
        except ConfluenceError as e:
            logger.exception("Confluence test connection failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/spaces",
        response_model=ConfluenceSpacesResponse,
        tags=["Confluence"],
    )
    def confluence_spaces(request: ConfluenceSpacesRequest):
        """List accessible Confluence spaces."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                spaces = client.list_spaces(limit=request.limit)
            return ConfluenceSpacesResponse(
                spaces=[
                    ConfluenceSpaceItem(
                        key=str(s.get("key", "")), name=str(s.get("name", ""))
                    )
                    for s in spaces
                ]
            )
        except ConfluenceError as e:
            logger.exception("Confluence list spaces failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/pages",
        response_model=ConfluencePagesResponse,
        tags=["Confluence"],
    )
    def confluence_pages(request: ConfluencePagesRequest):
        """List Confluence pages in a space or under a parent page."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                data = client.list_pages(
                    space_key=request.space_key,
                    parent_page_id=request.parent_page_id,
                    start=request.start,
                    limit=request.limit,
                )
            base = request.base_url.rstrip("/")
            pages = []
            for p in data.get("results", []):
                pid = str(p.get("id", ""))
                pages.append(
                    ConfluencePageItem(
                        id=pid,
                        title=str(p.get("title", "")),
                        space_key=str((p.get("space") or {}).get("key", "")),
                        url=f"{base}/pages/viewpage.action?pageId={pid}",
                        version=str((p.get("version") or {}).get("number", "")) or None,
                    )
                )
            return ConfluencePagesResponse(
                pages=pages,
                has_more=bool(data.get("_links", {}).get("next")),
            )
        except ConfluenceError as e:
            logger.exception("Confluence list pages failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/index",
        response_model=ConfluenceIndexResponse,
        tags=["Confluence"],
    )
    def confluence_index(request: ConfluenceIndexRequest):
        """Index Confluence pages (ids / space / subtree). Idempotent per page."""
        _check_allowed_host(request.base_url)
        try:
            with _make_client(request) as client:
                result = _index_with_client(request, client, ingestion, vector_store)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ConfluenceError as e:
            logger.exception("Confluence index failed")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post(
        "/confluence/sync",
        response_model=ConfluenceSyncResponse,
        tags=["Confluence"],
    )
    def confluence_sync(request: ConfluenceSyncRequest):
        """Re-index Confluence pages (same body as /index)."""
        return confluence_index(request)

    @router.get(
        "/confluence/status", response_model=ConfluenceStatusResponse, tags=["Confluence"]
    )
    def confluence_status():
        """Last Confluence sync status."""
        if not _CONFLUENCE_LOG_PATH.exists():
            return ConfluenceStatusResponse()
        try:
            entry = json.loads(_CONFLUENCE_LOG_PATH.read_text(encoding="utf-8"))
            return ConfluenceStatusResponse(
                last_sync=entry.get("last_sync"),
                duration_seconds=entry.get("duration_seconds"),
                pages_indexed=entry.get("pages_indexed"),
                pages_failed=entry.get("pages_failed"),
                chunks_ingested=entry.get("chunks_ingested"),
                error=entry.get("error"),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read Confluence sync log: %s", e)
            return ConfluenceStatusResponse()

    return router
