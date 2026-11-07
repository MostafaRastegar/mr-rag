"""
Minimal mock Confluence REST API for test data.

Implements enough of /rest/api/* to exercise the Confluence integration:
  GET /rest/api/user/current
  GET /rest/api/space
  GET /rest/api/content  (spaceKey, type=page, status=current, start, limit, expand)
  GET /rest/api/content/{id}  (expand)
  GET /rest/api/content/{id}/child/page

Auth: Authorization: Bearer <CONFLUENCE_MOCK_TOKEN>
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Confluence Mock")

TOKEN = os.environ.get("CONFLUENCE_MOCK_TOKEN", "test-token")
BASE_DIR = Path(__file__).resolve().parent
PAGES_FILE = BASE_DIR / ".." / "confluence" / "pages.json"

with open(PAGES_FILE, encoding="utf-8") as f:
    PAGES = json.load(f)

PAGES_BY_ID = {str(p["id"]): p for p in PAGES}


def _require_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/rest/api/user/current")
def current_user(authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    return {"displayName": "Test User", "username": "testuser"}


@app.get("/rest/api/space")
def list_spaces(authorization: str | None = Header(default=None), limit: int = 100):
    _require_auth(authorization)
    spaces = {}
    for p in PAGES:
        spaces[p["space_key"]] = {"key": p["space_key"], "name": p["space_key"]}
    return {
        "results": list(spaces.values())[:limit],
        "size": len(spaces),
        "start": 0,
        "limit": limit,
        "_links": {},
    }


def _page_response(page: dict, expand: str = "") -> dict:
    base = {
        "id": page["id"],
        "title": page["title"],
        "type": "page",
        "status": "current",
        "space": {"key": page["space_key"], "name": page["space_key"]},
        "version": {"number": page.get("version", 1), "when": "2026-01-01T00:00:00Z"},
        "ancestors": [{"id": a} for a in page.get("ancestors", [])],
        "body": {
            "storage": {
                "value": page.get("body", ""),
                "representation": "storage",
            }
        },
        "_links": {"webui": f"/pages/viewpage.action?pageId={page['id']}"},
    }
    return base


@app.get("/rest/api/content")
def list_content(
    authorization: str | None = Header(default=None),
    spaceKey: str | None = None,
    type: str | None = None,
    status: str | None = None,
    start: int = 0,
    limit: int = 100,
    expand: str = "",
):
    _require_auth(authorization)
    results = []
    for p in PAGES:
        if spaceKey and p["space_key"] != spaceKey:
            continue
        if type and p.get("type", "page") != type:
            continue
        if status and p.get("status", "current") != status:
            continue
        results.append(_page_response(p, expand))

    total = len(results)
    page = results[start : start + limit]
    has_next = start + limit < total

    return {
        "results": page,
        "size": len(page),
        "start": start,
        "limit": limit,
        "total": total,
        "_links": {"next": f"?start={start + limit}&limit={limit}" if has_next else None},
    }


@app.get("/rest/api/content/{page_id}")
def get_content(page_id: str, authorization: str | None = Header(default=None), expand: str = ""):
    _require_auth(authorization)
    page = PAGES_BY_ID.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return _page_response(page, expand)


@app.get("/rest/api/content/{page_id}/child/page")
def child_pages(page_id: str, authorization: str | None = Header(default=None), start: int = 0, limit: int = 100):
    _require_auth(authorization)
    children = [p for p in PAGES if page_id in p.get("ancestors", [])]
    results = [_page_response(p) for p in children]
    page = results[start : start + limit]
    has_next = start + limit < len(results)
    return {
        "results": page,
        "size": len(page),
        "start": start,
        "limit": limit,
        "total": len(results),
        "_links": {"next": f"?start={start + limit}&limit={limit}" if has_next else None},
    }
