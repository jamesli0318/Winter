from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime

from src.twitter.models import RawTweet

logger = logging.getLogger(__name__)


class TweetCache:
    """SQLite-backed tweet cache for deduplication."""

    def __init__(self, db_path: str = "data/cache.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                tweet_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                text TEXT,
                created_at TEXT,
                url TEXT,
                fetched_at TEXT NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tweets_username ON tweets(username)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at)
        """)
        self.conn.commit()

    def has_tweet(self, tweet_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM tweets WHERE tweet_id = ?", (tweet_id,)
        ).fetchone()
        return row is not None

    def insert_tweet(self, tweet: RawTweet) -> None:
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO tweets (tweet_id, username, text, created_at, url, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    tweet.tweet_id,
                    tweet.username,
                    tweet.text,
                    tweet.created_at.isoformat(),
                    tweet.url,
                    datetime.utcnow().isoformat(),
                ),
            )
            self.conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to cache tweet %s", tweet.tweet_id)

    def cleanup(self, days: int = 30) -> int:
        """Remove tweets older than `days`."""
        cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0)
        from datetime import timedelta
        cutoff = (cutoff - timedelta(days=days)).isoformat()
        cursor = self.conn.execute("DELETE FROM tweets WHERE created_at < ?", (cutoff,))
        self.conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Cleaned up %d old cached tweets", deleted)
        return deleted

    def close(self) -> None:
        self.conn.close()
