"""
Confluence ingestion service.

Idempotent: before indexing a page, previous chunks with the same `page_id`
are deleted from the vector store. One failing page never aborts the whole
index; errors are collected and returned.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from app.core.ports import VectorStorePort
from app.core.domain import Document
from app.infrastructure.confluence_client import ConfluenceClient
from app.pipeline.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)

_LOG_PATH = Path("data/confluence_sync_log.json")


@dataclass
class IndexResult:
    pages_indexed: int = 0
    pages_failed: int = 0
    chunks_ingested: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)


class ConfluenceIngestionService:
    def __init__(
        self,
        pipeline: IngestionPipeline,
        vector_store: VectorStorePort,
        max_pages: int = 2000,
    ) -> None:
        self._pipeline = pipeline
        self._vector_store = vector_store
        self._max_pages = max_pages

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def index(
        self,
        client: ConfluenceClient,
        mode: str,
        page_ids: List[str] | None = None,
        space_key: str | None = None,
        root_page_id: str | None = None,
        recursive: bool = False,
    ) -> IndexResult:
        """
        Index Confluence pages.

        mode:
          - "ids"      : explicit page_ids
          - "space"    : all pages in space_key
          - "subtree"  : root_page_id and (optionally) all descendants
        """
        result = IndexResult()
        started = time.time()

        try:
            pages = self._collect_pages(
                client, mode, page_ids, space_key, root_page_id, recursive
            )
        except Exception as e:
            logger.exception("Failed to discover Confluence pages")
            result.errors.append(
                {"page_id": "discovery", "page_title": "discovery", "error": str(e)}
            )
            self._write_log(result, started, error=str(e))
            return result

        for item in pages:
            page_id = str(item.get("id", ""))
            title = item.get("title", "untitled")
            try:
                # 'ids' mode returns placeholder dicts; fetch the full page here
                # so a single bad page id is isolated instead of aborting discovery.
                page = (
                    client.get_page(page_id)
                    if item.get("_placeholder")
                    else item
                )
                doc_dict = client.page_to_document(page, client.base_url or "")
                doc = Document(
                    content=doc_dict["content"], metadata=doc_dict["metadata"]
                )

                # Idempotent: remove previous chunks for this page before adding.
                if page_id:
                    removed = self._vector_store.delete_by_metadata(
                        "page_id", page_id
                    )
                    logger.debug(
                        "Removed %d old chunks for page %s", removed, page_id
                    )

                stored = self._pipeline.run_documents(
                    [doc],
                    original_filename=f"confluence:{page_id}",
                    source_path=doc_dict["metadata"]["url"],
                )
                result.pages_indexed += 1
                result.chunks_ingested += stored
                logger.info(
                    "Indexed Confluence page %s (%s): %d chunks", page_id, title, stored
                )
            except Exception as e:
                result.pages_failed += 1
                result.errors.append(
                    {"page_id": page_id, "page_title": title, "error": str(e)}
                )
                logger.warning("Failed to index page %s: %s", page_id, e)

        self._write_log(result, started)
        return result

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def _collect_pages(
        self,
        client: ConfluenceClient,
        mode: str,
        page_ids: List[str] | None,
        space_key: str | None,
        root_page_id: str | None,
        recursive: bool,
    ) -> List[Dict[str, Any]]:
        pages: List[Dict[str, Any]] = []

        if mode == "ids":
            # Return placeholders; full pages are fetched inside the per-page
            # try block so one bad page id never aborts the whole index.
            for pid in page_ids or []:
                pages.append({"id": pid, "_placeholder": True})
        elif mode == "space":
            pages.extend(client.iter_pages(space_key=space_key, max_pages=self._max_pages))
        elif mode == "subtree":
            pages.extend(self._iter_subtree(client, root_page_id, recursive))
        else:
            raise ValueError(f"Unknown index mode: {mode}")

        return pages

    def _iter_subtree(
        self, client: ConfluenceClient, root_page_id: str | None, recursive: bool
    ) -> List[Dict[str, Any]]:
        """BFS over child pages starting at root_page_id."""
        if not root_page_id:
            return []
        pages: List[Dict[str, Any]] = []
        seen: set[str] = set()
        stack: List[str] = [root_page_id]

        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                page = client.get_page(pid)
            except Exception as e:
                logger.warning("Failed to fetch subtree page %s: %s", pid, e)
                continue
            pages.append(page)

            if recursive:
                start = 0
                limit = 100
                while True:
                    data = client.list_pages(
                        parent_page_id=pid, start=start, limit=limit
                    )
                    children = data.get("results", [])
                    for child in children:
                        cid = str(child.get("id", ""))
                        if cid and cid not in seen:
                            stack.append(cid)
                    if not data.get("_links", {}).get("next"):
                        break
                    start += len(children)

        return pages

    # ------------------------------------------------------------------ #
    # Status log
    # ------------------------------------------------------------------ #
    def _write_log(self, result: IndexResult, started: float, error: str | None = None) -> None:
        entry: Dict[str, Any] = {
            "last_sync": time.time(),
            "duration_seconds": round(time.time() - started, 2),
            "pages_indexed": result.pages_indexed,
            "pages_failed": result.pages_failed,
            "chunks_ingested": result.chunks_ingested,
            "errors": result.errors,
        }
        if error:
            entry["error"] = error
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.warning("Failed to write Confluence sync log: %s", e)


if __name__ == "__main__":
    # Minimal self-check: service maps a fake page to a document with expected keys.
    from app.core.domain import Document  # noqa: F401  (already imported)

    class _StubPipeline:
        def run_documents(self, documents, **_kwargs) -> int:
            assert documents and documents[0].content
            return len(documents)

    class _StubVS:
        def delete_by_metadata(self, key: str, value: str) -> int:
            assert key == "page_id"
            return 0

    import sys

    sys.path.insert(0, ".")
    client = ConfluenceClient("http://example.com", auth_type="bearer", token="t")
    page = {
        "id": "123",
        "title": "Demo Page",
        "version": {"number": 2, "when": "2026-01-01"},
        "space": {"key": "DEMO"},
        "body": {"storage": {"value": "<p>Hello world</p>"}},
        "ancestors": [],
    }
    doc = client.page_to_document(page, "http://example.com")
    assert doc["metadata"]["page_id"] == "123"
    assert doc["metadata"]["original_filename"] == "confluence:123"
    assert "Hello world" in doc["content"]
    assert doc["metadata"]["url"] == "http://example.com/pages/viewpage.action?pageId=123"
    print("confluence_ingestion self-check: OK")
