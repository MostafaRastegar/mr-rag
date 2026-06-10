"""
Scraper API client.

Fetches data from the external Scraper API with pagination support.
"""

import logging
from typing import Any, Dict, List

import httpx

from app.scheduler.auth import ScraperAuth
from app.scheduler.config import scheduler_settings

logger = logging.getLogger(__name__)


class ScraperClientError(Exception):
    """Raised when a Scraper API request fails."""


class ScraperClient:
    """
    Client for fetching data from the external Scraper API.

    Handles pagination automatically and fetches all pages.
    """

    def __init__(self, auth: ScraperAuth) -> None:
        self._auth = auth
        self._base_url = scheduler_settings.scraper_api_url

    def search_messages(self, page: int = 1) -> Dict[str, Any]:
        """
        Fetch one page of messages from the Scraper API.

        Args:
            page: Page number to fetch (1-indexed).

        Returns:
            The full response dict with keys:
            total_results, current_page, page_size, total_pages, results.
        """
        token = self._auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}

        url = f"{self._base_url}/api/v1/messages/search/"
        params = {"page": page}

        try:
            response = httpx.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Fetched page %d/%d (%d results)",
                data.get("current_page", page),
                data.get("total_pages", 1),
                len(data.get("results", [])),
            )
            return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Scraper API error on page %d: %s - %s",
                page,
                e.response.status_code,
                e.response.text,
            )
            raise ScraperClientError(
                f"Scraper API returned {e.response.status_code}: {e.response.text}"
            ) from e

        except httpx.RequestError as e:
            logger.error("Scraper API request failed: %s", str(e))
            raise ScraperClientError(f"Scraper API request failed: {e}") from e

    def fetch_all(self) -> List[Dict[str, Any]]:
        """
        Fetch all pages of messages from the Scraper API.

        Iterates through all pages and aggregates the results.

        Returns:
            A flat list of all message dicts across all pages.
        """
        all_results: List[Dict[str, Any]] = []
        page = 1

        while True:
            data = self.search_messages(page)
            results = data.get("results", [])
            all_results.extend(results)

            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        logger.info("Fetched total %d messages across %d pages", len(all_results), page)
        return all_results
