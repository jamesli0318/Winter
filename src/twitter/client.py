from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://twitter-api45.p.rapidapi.com"
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFFS = [5, 15, 30]


class TwitterClient:
    """RapidAPI Twitter API45 client using httpx."""

    def __init__(self, rapidapi_key: str):
        self._headers = {
            "x-rapidapi-host": "twitter-api45.p.rapidapi.com",
            "x-rapidapi-key": rapidapi_key,
        }
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self._headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def get_timeline(self, username: str) -> list[dict]:
        """Fetch recent tweets for a user via timeline.php."""
        data = await self._request("/timeline.php", params={"screenname": username})
        return data.get("timeline", [])

    async def get_user_profile(self, username: str) -> dict:
        """Fetch user profile via screenname.php."""
        return await self._request("/screenname.php", params={"screenname": username})

    async def search_users(self, query: str) -> list[dict]:
        """Search for users via search.php with search_type=People."""
        data = await self._request(
            "/search.php",
            params={"query": query, "search_type": "People"},
        )
        return data.get("timeline", [])

    async def _request(self, path: str, params: dict) -> dict:
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                resp = await self._http.get(path, params=params)
                if resp.status_code == 429:
                    raise RateLimitError(f"429 Too Many Requests for {path}")
                resp.raise_for_status()
                return resp.json()
            except RateLimitError:
                if attempt >= RATE_LIMIT_RETRIES:
                    raise
                wait = RATE_LIMIT_BACKOFFS[min(attempt, len(RATE_LIMIT_BACKOFFS) - 1)]
                logger.warning(
                    "Rate limited on %s (attempt %d/%d), waiting %ds",
                    path, attempt + 1, RATE_LIMIT_RETRIES, wait,
                )
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                logger.error("HTTP %d on %s: %s", e.response.status_code, path, e.response.text[:200])
                raise
        raise RuntimeError("Exhausted retries")


class RateLimitError(Exception):
    pass
