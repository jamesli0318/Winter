from __future__ import annotations

import logging

from src.grouping.algorithm import run_algorithm
from src.grouping.models import Event
from src.twitter.models import RawTweet

logger = logging.getLogger(__name__)


async def group_tweets(tweets: list[RawTweet]) -> list[Event]:
    """Group tweets into events using rule-based algorithmic clustering."""
    if not tweets:
        return []

    events = run_algorithm(tweets)
    logger.info("Grouped %d tweets into %d events", len(tweets), len(events))
    return events
