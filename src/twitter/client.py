from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://twitter241.p.rapidapi.com"
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFFS = [5, 15, 30]


class TwitterClient:
    """RapidAPI Twttr API (twitter241) client using httpx."""

    def __init__(self, rapidapi_key: str):
        self._headers = {
            "x-rapidapi-host": "twitter241.p.rapidapi.com",
            "x-rapidapi-key": rapidapi_key,
        }
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=self._headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def get_user_profile(self, username: str) -> dict:
        """Fetch user profile via /user endpoint.

        Returns a flat dict compatible with old API field names:
        {screen_name, name, desc, description, sub_count, followers, rest_id}
        """
        data = await self._request("/user", params={"username": username})
        user_result = (
            data.get("result", {})
            .get("data", {})
            .get("user", {})
            .get("result", {})
        )
        return self._flatten_user(user_result)

    async def get_timeline(self, username: str) -> list[dict]:
        """Fetch recent tweets for a user.

        Two-step: get rest_id from profile, then fetch /user-tweets.
        Returns list of flat tweet dicts compatible with old API field names.
        """
        profile = await self.get_user_profile(username)
        rest_id = profile.get("rest_id")
        if not rest_id:
            logger.warning("No rest_id for @%s, cannot fetch timeline", username)
            return []

        data = await self._request(
            "/user-tweets", params={"user": rest_id, "count": "40"}
        )
        return self._parse_timeline_entries(data)

    async def search_users(self, query: str) -> list[dict]:
        """Search for users via /search with type=People.

        Returns list of flat user dicts compatible with old API field names.
        """
        data = await self._request(
            "/search", params={"query": query, "type": "People", "count": "20"}
        )
        entries = self._extract_entries(data)
        users = []
        for entry in entries:
            user_result = (
                entry.get("content", {})
                .get("itemContent", {})
                .get("user_results", {})
                .get("result", {})
            )
            if user_result and user_result.get("__typename") == "User":
                users.append(self._flatten_user(user_result))
        return users

    # ── GraphQL response helpers ─────────────────────────────────

    @staticmethod
    def _flatten_user(user_result: dict) -> dict:
        """Flatten a GraphQL user result into old-API-compatible dict.

        NOTE: In search results, legacy.screen_name/name are null.
              Always prefer core.screen_name / core.name.
        """
        core = user_result.get("core", {})
        legacy = user_result.get("legacy", {})
        description = legacy.get("description", "")

        return {
            "screen_name": core.get("screen_name") or legacy.get("screen_name", ""),
            "name": core.get("name") or legacy.get("name", ""),
            "desc": description,
            "description": description,
            "sub_count": legacy.get("followers_count", 0),
            "followers": legacy.get("followers_count", 0),
            "rest_id": user_result.get("rest_id", ""),
        }

    @staticmethod
    def _flatten_tweet(tweet_result: dict) -> dict:
        """Flatten a GraphQL tweet result into old-API-compatible dict."""
        legacy = tweet_result.get("legacy", {})
        user_obj = (
            tweet_result.get("core", {})
            .get("user_results", {})
            .get("result", {})
        )
        user_core = user_obj.get("core", {})

        # Media: convert extended_entities.media → {photo: [], video: []}
        media: dict[str, list] = {"photo": [], "video": []}
        for m in (legacy.get("extended_entities") or {}).get("media", []):
            url = m.get("media_url_https", "")
            if not url:
                continue
            if m.get("type") == "photo":
                media["photo"].append({"media_url_https": url})
            elif m.get("type") in ("video", "animated_gif"):
                media["video"].append({"media_url_https": url})

        # Retweet detection
        retweeted = (
            legacy.get("retweeted_status_result")
            or tweet_result.get("retweeted_status_result")
            or None
        )

        # Quote tweet (full text may not be available)
        quoted_tweet = None
        if legacy.get("is_quote_status"):
            quoted_id = legacy.get("quoted_status_id_str")
            quoted_result = (
                tweet_result.get("quoted_status_result", {}).get("result", {})
            )
            quoted_text = quoted_result.get("legacy", {}).get("full_text")
            if quoted_id:
                quoted_tweet = {"tweet_id": quoted_id, "text": quoted_text}

        return {
            "tweet_id": legacy.get("id_str") or tweet_result.get("rest_id", ""),
            "text": legacy.get("full_text", ""),
            "created_at": legacy.get("created_at", ""),
            "favorites": legacy.get("favorite_count", 0),
            "retweets": legacy.get("retweet_count", 0),
            "retweeted_tweet": retweeted,
            "quoted_tweet": quoted_tweet,
            "media": media,
            "screen_name": user_core.get("screen_name") or "",
            "name": user_core.get("name") or "",
        }

    def _parse_timeline_entries(self, data: dict) -> list[dict]:
        """Parse timeline response into list of flat tweet dicts."""
        entries = self._extract_entries(data)
        tweets = []
        for entry in entries:
            tweet_result = (
                entry.get("content", {})
                .get("itemContent", {})
                .get("tweet_results", {})
                .get("result", {})
            )
            if not tweet_result:
                continue
            typename = tweet_result.get("__typename", "")
            if typename not in ("Tweet", "TweetWithVisibilityResults"):
                continue
            # TweetWithVisibilityResults wraps the actual tweet
            if typename == "TweetWithVisibilityResults":
                tweet_result = tweet_result.get("tweet", tweet_result)
            tweets.append(self._flatten_tweet(tweet_result))
        return tweets

    @staticmethod
    def _extract_entries(data: dict) -> list[dict]:
        """Extract entries from GraphQL timeline instructions."""
        instructions = (
            data.get("result", {})
            .get("timeline", {})
            .get("instructions", [])
        )
        entries: list[dict] = []
        for instruction in instructions:
            inst_type = instruction.get("type", "")
            if inst_type == "TimelineAddEntries":
                entries.extend(instruction.get("entries", []))
            elif inst_type == "TimelinePinEntry":
                entry = instruction.get("entry")
                if entry:
                    entries.append(entry)
        return entries

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
