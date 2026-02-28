from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from src.twitter.client import TwitterClient
from src.twitter.models import AccountType, TrackedAccount

logger = logging.getLogger(__name__)

# Keywords used to classify account type from bio
OFFICIAL_KEYWORDS = re.compile(r"official|공식|SM Entertainment|에스파|aespa", re.IGNORECASE)
FANSITE_KEYWORDS = re.compile(r"fansite|팬사이트|fan account|masternim|마스터", re.IGNORECASE)
TRANSLATOR_KEYWORDS = re.compile(r"trans|번역|翻訳|翻譯|eng sub|subtitle", re.IGNORECASE)
NEWS_KEYWORDS = re.compile(r"news|update|chart|data|info|정보|소식|daily|vote|投票", re.IGNORECASE)

WINTER_TWEET_KEYWORDS = re.compile(
    r"winter|윈터|ウィンター|민정|minjeong|김민정",
    re.IGNORECASE,
)

INTER_SEARCH_DELAY = 3  # seconds between search queries
TWEET_SAMPLE_SIZE = 40


def _classify_account(bio: str) -> AccountType:
    if OFFICIAL_KEYWORDS.search(bio):
        return AccountType.OFFICIAL
    if FANSITE_KEYWORDS.search(bio):
        return AccountType.FANSITE
    if TRANSLATOR_KEYWORDS.search(bio):
        return AccountType.TRANSLATOR
    if NEWS_KEYWORDS.search(bio):
        return AccountType.NEWS
    return AccountType.OTHER


async def discover_accounts(
    client: TwitterClient,
    keywords: list[str],
    min_followers: int = 500,
    min_winter_ratio: float = 0.25,
    max_accounts: int = 25,
    seed_accounts: list[str] | None = None,
) -> list[TrackedAccount]:
    """Search Twitter for Winter-related accounts and filter them."""
    candidates: dict[str, TrackedAccount] = {}

    # Seed accounts are always included
    for screen_name in (seed_accounts or []):
        try:
            profile = await client.get_user_profile(screen_name)
            account = TrackedAccount(
                username=profile.get("screen_name", screen_name),
                display_name=profile.get("name", screen_name),
                account_type=_classify_account(profile.get("desc", "") or profile.get("description", "")),
                followers=int(profile.get("sub_count", 0) or 0),
                winter_ratio=1.0,
                discovered_at=datetime.now(timezone.utc).isoformat(),
                is_seed=True,
            )
            candidates[screen_name.lower()] = account
            logger.info("Added seed account @%s", screen_name)
            await asyncio.sleep(1)
        except Exception:
            logger.warning("Could not look up seed account @%s", screen_name)

    # Search for accounts matching each keyword
    for keyword in keywords:
        try:
            results = await client.search_users(keyword)
            for user in results:
                sn = (user.get("screen_name", "") or "").lower()
                if not sn or sn in candidates:
                    continue

                followers = int(user.get("sub_count", 0) or user.get("followers", 0) or 0)
                if followers < min_followers:
                    continue

                bio = user.get("desc", "") or user.get("description", "") or ""
                account_type = _classify_account(bio)

                candidates[sn] = TrackedAccount(
                    username=user.get("screen_name", sn),
                    display_name=user.get("name", sn),
                    account_type=account_type,
                    followers=followers,
                    winter_ratio=0.0,  # will compute below
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                )
            logger.info("Searched '%s': found %d candidates so far", keyword, len(candidates))
        except Exception:
            logger.warning("Search failed for keyword '%s'", keyword)
        await asyncio.sleep(INTER_SEARCH_DELAY)

    # Compute winter_ratio for non-seed accounts
    for sn, account in list(candidates.items()):
        if account.is_seed:
            continue
        try:
            ratio = await _compute_winter_ratio(client, account.username)
            account.winter_ratio = ratio
            await asyncio.sleep(2)
        except Exception:
            logger.warning("Could not compute winter_ratio for @%s", account.username)
            account.winter_ratio = 0.0

    # Filter: min ratio, sort by followers, cap at max
    filtered = [
        a for a in candidates.values()
        if a.is_seed or a.winter_ratio >= min_winter_ratio
    ]
    filtered.sort(key=lambda a: (a.is_seed, a.followers), reverse=True)
    result = filtered[:max_accounts]

    logger.info(
        "Discovery complete: %d accounts from %d candidates",
        len(result),
        len(candidates),
    )
    return result


async def _compute_winter_ratio(client: TwitterClient, screen_name: str) -> float:
    """Sample recent tweets and compute what fraction mention Winter."""
    try:
        tweets = await client.get_timeline(screen_name)
    except Exception:
        return 0.0

    total = 0
    hits = 0
    for tweet in tweets[:TWEET_SAMPLE_SIZE]:
        # Skip retweets (RapidAPI marks them with retweeted_tweet or RT prefix)
        if tweet.get("retweeted_tweet") or (tweet.get("text", "").startswith("RT @")):
            continue
        total += 1
        text = tweet.get("text", "")
        if WINTER_TWEET_KEYWORDS.search(text):
            hits += 1

    if total == 0:
        return 0.0
    return hits / total
