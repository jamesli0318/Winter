from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from src.twitter.client import TwitterClient
from src.twitter.models import AccountType, RawTweet, TrackedAccount
from src.storage.cache import TweetCache

logger = logging.getLogger(__name__)

# Keywords to filter news account tweets for Winter relevance
WINTER_KEYWORDS = re.compile(
    r"winter|윈터|ウィンター|민정|minjeong|김민정",
    re.IGNORECASE,
)

INTER_ACCOUNT_DELAY = 2  # seconds between fetching different accounts


def _tweet_url(username: str, tweet_id: str) -> str:
    return f"https://x.com/{username}/status/{tweet_id}"


def _is_winter_relevant(text: str) -> bool:
    return bool(WINTER_KEYWORDS.search(text))


def _parse_tweet_time(created_at_str: str | None) -> datetime | None:
    if not created_at_str:
        return None
    try:
        # Twitter format: "Wed Oct 10 20:19:24 +0000 2024"
        return datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        pass
    try:
        # ISO format fallback
        return datetime.fromisoformat(created_at_str)
    except (ValueError, TypeError):
        pass
    return None


def _extract_media_urls(tweet: dict) -> list[str]:
    media = tweet.get("media") or {}
    urls: list[str] = []

    # Handle media.photo list
    for photo in media.get("photo", []):
        url = photo.get("media_url_https", "")
        if url:
            urls.append(url)

    # Handle media.video list
    for video in media.get("video", []):
        url = video.get("media_url_https", "")
        if url:
            urls.append(url)

    return urls


async def collect_tweets(
    client: TwitterClient,
    accounts: list[TrackedAccount],
    cache: TweetCache,
    hours: int = 24,
    tz: timezone | None = None,
) -> list[RawTweet]:
    """Fetch tweets from all tracked accounts within the past `hours`.

    - News accounts are filtered for Winter keywords.
    - Pure retweets are skipped.
    - Results are deduplicated via the SQLite cache.
    """
    if tz is None:
        tz = timezone.utc
    cutoff = datetime.now(tz) - timedelta(hours=hours)
    all_tweets: list[RawTweet] = []

    for account in accounts:
        try:
            tweets = await _fetch_account_tweets(client, account, cutoff, cache)
            all_tweets.extend(tweets)
            logger.info("Collected %d tweets from @%s", len(tweets), account.username)
        except Exception:
            logger.exception("Failed to fetch tweets from @%s, skipping", account.username)
        await asyncio.sleep(INTER_ACCOUNT_DELAY)

    logger.info("Total collected: %d tweets from %d accounts", len(all_tweets), len(accounts))
    return all_tweets


async def _fetch_account_tweets(
    client: TwitterClient,
    account: TrackedAccount,
    cutoff: datetime,
    cache: TweetCache,
) -> list[RawTweet]:
    timeline = await client.get_timeline(account.username)
    tweets: list[RawTweet] = []

    for tweet in timeline:
        # Skip pure retweets
        if tweet.get("retweeted_tweet") or (tweet.get("text", "").startswith("RT @")):
            continue

        # Parse timestamp
        created_at = _parse_tweet_time(tweet.get("created_at"))
        if created_at is None or created_at < cutoff:
            continue

        text = tweet.get("text", "")
        tweet_id = str(tweet.get("tweet_id", ""))
        if not tweet_id:
            continue

        # Only keep Winter-relevant tweets (all accounts)
        if not _is_winter_relevant(text):
            continue

        # Dedup via cache
        if cache.has_tweet(tweet_id):
            continue

        raw = RawTweet(
            tweet_id=tweet_id,
            username=account.username,
            display_name=account.display_name or account.username,
            account_type=account.account_type,
            text=text,
            created_at=created_at,
            url=_tweet_url(account.username, tweet_id),
            is_retweet=False,
            is_quote=bool(tweet.get("quoted_tweet")),
            quoted_text=tweet.get("quoted_tweet", {}).get("text") if tweet.get("quoted_tweet") else None,
            media_urls=_extract_media_urls(tweet),
            like_count=int(tweet.get("favorites", 0) or 0),
            retweet_count=int(tweet.get("retweets", 0) or 0),
        )
        tweets.append(raw)
        cache.insert_tweet(raw)

    return tweets
