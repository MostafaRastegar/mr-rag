"""
JWT Authentication for the external Scraper API.

Handles token acquisition and caching with expiry checking.
"""

import logging
import time

import httpx

from app.scheduler.config import scheduler_settings

logger = logging.getLogger(__name__)


class ScraperAuth:
    """
    Manages JWT authentication for the Scraper API.

    Automatically refreshes the token when it expires.
    Caches the token in memory with its expiry timestamp.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._base_url = base_url or scheduler_settings.scraper_api_url
        self._username = username or scheduler_settings.scraper_username
        self._password = password or scheduler_settings.scraper_password
        self._token: str | None = None
        self._token_expiry: float = 0.0  # timestamp when token expires

    def get_token(self) -> str:
        """
        Get a valid JWT token.

        If no token exists or it has expired, fetches a new one.

        Returns:
            A valid JWT access token string.

        Raises:
            ScraperAuthError: If authentication fails.
        """
        if self._is_valid():
            return self._token  # type: ignore[return-value]
        return self._refresh()

    def _is_valid(self) -> bool:
        """Check if the current token is still valid."""
        return self._token is not None and time.time() < self._token_expiry

    def _refresh(self) -> str:
        """
        Fetch a new JWT token from the Scraper API.

        Returns:
            A fresh JWT access token.

        Raises:
            ScraperAuthError: If the API returns an error.
        """
        url = f"{self._base_url}/api/v1/token/"
        payload = {"username": self._username, "password": self._password}

        logger.info("Authenticating with Scraper API: %s", url)

        try:
            response = httpx.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            self._token = data["access"]
            if not self._token:
                raise ScraperAuthError("Scraper API returned empty token")
            # Default JWT expiry is 24h; if API returns a different field,
            # parse it here. For now we cache with a 23-hour TTL.
            self._token_expiry = time.time() + (23 * 3600)
            logger.info("Scraper API authentication successful")
            return self._token

        except httpx.HTTPStatusError as e:
            logger.error(
                "Scraper auth failed: %s - %s",
                e.response.status_code,
                e.response.text,
            )
            raise ScraperAuthError(
                f"Scraper auth failed: {e.response.status_code}: {e.response.text}"
            ) from e

        except httpx.RequestError as e:
            logger.error("Scraper auth request failed: %s", str(e))
            raise ScraperAuthError(f"Scraper auth request failed: {e}") from e

    def clear(self) -> None:
        """Clear the cached token, forcing a refresh on next get_token()."""
        self._token = None
        self._token_expiry = 0.0


class ScraperAuthError(Exception):
    """Raised when Scraper API authentication fails."""
