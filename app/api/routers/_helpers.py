"""
Shared helpers used by multiple API routers.

Extracted from the monolithic routes.py so every router stays thin and
dependency-free where possible.
"""

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

from app.config import settings
from app.core.ports import VectorStorePort
from app.pipeline.confluence_ingestion import ConfluenceIngestionService
from app.infrastructure.confluence_client import ConfluenceClient
from app.api.schemas import ConfluenceIndexResponse

logger = logging.getLogger(__name__)

_CONFLUENCE_LOG_PATH = Path("data/confluence_sync_log.json")


def _source_label(metadata: dict | None) -> str | None:
    """
    Build a human-readable source label from chunk metadata.

    Prefers `original_filename` because chunks ingested from temp files carry a
    meaningless `source` such as `/tmp/tmpab12cd.txt`. Page and section are
    appended when present so a citation can be located in the source document.
    """
    if not metadata:
        return None

    name = metadata.get("original_filename") or metadata.get("source")
    if not name:
        return None

    label = str(name).split("/")[-1]
    if metadata.get("page") is not None:
        label = f"{label}, p.{metadata['page']}"
    elif metadata.get("section"):
        label = f"{label} — {metadata['section']}"
    return label


def _check_allowed_host(base_url: str) -> None:
    """Reject Confluence hosts not in CONFLUENCE_ALLOWED_HOSTS (SSRF guard)."""
    allowed = settings.confluence_allowed_hosts
    if not allowed:
        return
    host = (urlparse(base_url).hostname or "").lower()
    hosts = {h.strip().lower() for h in allowed.split(",") if h.strip()}
    if host not in hosts:
        raise HTTPException(
            status_code=400, detail=f"Confluence host not allowed: {host}"
        )


def _make_client(request) -> ConfluenceClient:
    return ConfluenceClient(
        request.base_url,
        auth_type=request.auth_type,
        token=request.token,
        email=request.email,
        username=request.username,
        timeout=settings.confluence_timeout_seconds,
    )


def _index_with_client(
    request,
    client: ConfluenceClient,
    ingestion,
    vector_store: VectorStorePort,
) -> ConfluenceIndexResponse:
    service = ConfluenceIngestionService(
        ingestion, vector_store, max_pages=settings.confluence_max_pages
    )
    result = service.index(
        client=client,
        mode=request.mode,
        page_ids=request.page_ids,
        space_key=request.space_key,
        root_page_id=request.root_page_id,
        recursive=request.recursive,
    )
    return ConfluenceIndexResponse(
        status="success",
        pages_indexed=result.pages_indexed,
        pages_failed=result.pages_failed,
        chunks_ingested=result.chunks_ingested,
        errors=result.errors,
    )
