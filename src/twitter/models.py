from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AccountType(Enum):
    OFFICIAL = "official"
    FANSITE = "fansite"
    TRANSLATOR = "translator"
    NEWS = "news"
    OTHER = "other"


@dataclass
class TrackedAccount:
    username: str
    display_name: str
    account_type: AccountType
    followers: int = 0
    winter_ratio: float = 0.0
    discovered_at: str = ""
    is_seed: bool = False

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "account_type": self.account_type.value,
            "followers": self.followers,
            "winter_ratio": self.winter_ratio,
            "discovered_at": self.discovered_at,
            "is_seed": self.is_seed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrackedAccount:
        return cls(
            username=data["username"],
            display_name=data["display_name"],
            account_type=AccountType(data["account_type"]),
            followers=data.get("followers", 0),
            winter_ratio=data.get("winter_ratio", 0.0),
            discovered_at=data.get("discovered_at", ""),
            is_seed=data.get("is_seed", False),
        )


@dataclass
class RawTweet:
    tweet_id: str
    username: str
    display_name: str
    account_type: AccountType
    text: str
    created_at: datetime
    url: str
    is_retweet: bool = False
    is_quote: bool = False
    quoted_text: str | None = None
    media_urls: list[str] = field(default_factory=list)
    like_count: int = 0
    retweet_count: int = 0

    def to_dict(self) -> dict:
        return {
            "tweet_id": self.tweet_id,
            "username": self.username,
            "display_name": self.display_name,
            "account_type": self.account_type.value,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
            "url": self.url,
            "is_retweet": self.is_retweet,
            "is_quote": self.is_quote,
            "quoted_text": self.quoted_text,
            "media_urls": self.media_urls,
            "like_count": self.like_count,
            "retweet_count": self.retweet_count,
        }
