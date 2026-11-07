"""
Confluence REST client.

Fetches pages from Confluence Server/Data Center (PAT bearer) or Confluence
Cloud (email + API token basic auth). Pure stdlib + httpx — no Confluence SDK.

Auth:
  bearer   → Authorization: Bearer <token>            (Server/DC PAT)
  basic    → Authorization: Basic base64(email:token) (Cloud)

API prefix detected from host (`.atlassian.net` → /wiki/rest/api) unless
overridden explicitly.
"""

import base64
import logging
import time
from html.parser import HTMLParser
from typing import Any, Dict, Iterator, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ConfluenceError(Exception):
    """Raised when a Confluence request fails."""


class _TextExtractor(HTMLParser):
    """Small HTML→text converter: keeps whitespace/newlines, drops tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: List[str] = []
        self._skip_depth = 0
        self._skip = {"script", "style", "noscript"}

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")
        if tag in self._skip:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._parts.append(data)

    def get_text(self) -> str:
        text = "".join(self._parts)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


class ConfluenceClient:
    """Minimal Confluence REST client with pagination and retry/backoff."""

    def __init__(
        self,
        base_url: str,
        auth_type: str = "bearer",
        token: str = "",
        email: str | None = None,
        username: str | None = None,
        api_prefix: str | None = None,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_type = auth_type
        self._token = token
        self._email = email
        self._username = username
        self._api_prefix = api_prefix or self._detect_prefix(base_url)
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def _auth_header(self) -> Dict[str, str]:
        if self._auth_type == "basic":
            credentials = f"{self._email or self._username}:{self._token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{self._api_prefix}{path}"
        headers = self._auth_header()
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(url, headers=headers, params=params)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after
                        else self._retry_delay * (2 ** attempt)
                    )
                    logger.warning("Confluence rate limited, retrying in %ss", delay)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500 and attempt < self._max_retries:
                    time.sleep(self._retry_delay * (2 ** attempt))
                    continue
                raise ConfluenceError(
                    f"Confluence {e.response.status_code}: {e.response.text}"
                ) from e
            except httpx.RequestError as e:
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * (2 ** attempt))
                    continue
                raise ConfluenceError(f"Confluence request failed: {e}") from e

        raise ConfluenceError(str(last_error))  # type: ignore[arg-type]

    @property
    def base_url(self) -> str:
        return self._base_url

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ConfluenceClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _detect_prefix(base_url: str) -> str:
        return "/wiki/rest/api" if ".atlassian.net" in base_url else "/rest/api"

    def test_connection(self) -> Dict[str, Any]:
        """Validate credentials and base URL; returns user info."""
        return self._get("/user/current")

    def list_spaces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List accessible spaces."""
        data = self._get(
            "/space", params={"limit": limit, "expand": "description.plain"}
        )
        return data.get("results", [])

    def list_pages(
        self,
        space_key: str | None = None,
        parent_page_id: str | None = None,
        start: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List pages in a space, or children of a parent page."""
        params: Dict[str, Any] = {
            "type": "page",
            "status": "current",
            "start": start,
            "limit": limit,
            "expand": "version,space,ancestors",
        }
        if space_key:
            params["spaceKey"] = space_key
        if parent_page_id:
            return self._get(
                f"/content/{parent_page_id}/child/page", params=params
            )
        return self._get("/content", params=params)

    def iter_pages(
        self,
        space_key: str | None = None,
        parent_page_id: str | None = None,
        limit: int = 100,
        max_pages: int = 2000,
    ) -> Iterator[Dict[str, Any]]:
        """Yield all pages for a scope, paginating automatically."""
        start = 0
        fetched = 0
        while fetched < max_pages:
            data = self.list_pages(space_key, parent_page_id, start, limit)
            results = data.get("results", [])
            if not results:
                break
            for page in results:
                yield page
                fetched += 1
                if fetched >= max_pages:
                    return
            start += len(results)
            if not data.get("_links", {}).get("next"):
                break

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch one page with storage body and metadata."""
        return self._get(
            f"/content/{page_id}",
            params={"expand": "body.storage,version,ancestors,space"},
        )

    def page_to_document(self, page: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        """Convert a Confluence page JSON into a domain-style document dict."""
        page_id = str(page["id"])
        version = page.get("version", {})
        space = page.get("space", {})
        body = page.get("body", {}).get("storage", {}).get("value", "")

        ancestors = page.get("ancestors", [])
        parent_id = str(ancestors[-1]["id"]) if ancestors else None

        return {
            "content": html_to_text(body),
            "metadata": {
                "page_id": page_id,
                "space_key": space.get("key", ""),
                "page_title": page.get("title", ""),
                "page_version": str(version.get("number", "")),
                "last_modified": str(version.get("when", "")),
                "url": f"{base_url}/pages/viewpage.action?pageId={page_id}",
                "parent_page_id": parent_id or "",
                "source": page.get("title", ""),
                "original_filename": f"confluence:{page_id}",
                "file_type": "confluence",
            },
        }
