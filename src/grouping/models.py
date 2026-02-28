from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventCategory(Enum):
    SCHEDULE = "行程"
    MEDIA = "媒體"
    SNS = "SNS"
    NEWS = "新聞"

    @property
    def sort_order(self) -> int:
        return {
            EventCategory.SCHEDULE: 0,
            EventCategory.MEDIA: 1,
            EventCategory.SNS: 2,
            EventCategory.NEWS: 3,
        }[self]

    @property
    def emoji(self) -> str:
        return {
            EventCategory.SCHEDULE: "\U0001f4c5",  # calendar
            EventCategory.MEDIA: "\U0001f3ac",      # clapper
            EventCategory.SNS: "\U0001f4f1",        # phone
            EventCategory.NEWS: "\U0001f4f0",       # newspaper
        }[self]


@dataclass
class Event:
    name: str
    category: EventCategory
    summary: str
    tweet_ids: list[str] = field(default_factory=list)
    tweet_urls: list[str] = field(default_factory=list)
    earliest_time: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Event:
        category = data.get("category", "新聞")
        try:
            cat = EventCategory(category)
        except ValueError:
            cat = EventCategory.NEWS

        earliest = None
        if data.get("earliest_time"):
            try:
                earliest = datetime.fromisoformat(data["earliest_time"])
            except (ValueError, TypeError):
                pass

        return cls(
            name=data["name"],
            category=cat,
            summary=data.get("summary", ""),
            tweet_ids=data.get("tweet_ids", []),
            tweet_urls=data.get("tweet_urls", []),
            earliest_time=earliest,
        )
