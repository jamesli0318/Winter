from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.grouping.models import Event, EventCategory

TELEGRAM_MAX_LENGTH = 4096


def format_digest(
    events: list[Event],
    date_str: str | None = None,
    tz_name: str = "Asia/Taipei",
) -> list[str]:
    """Format events into Telegram HTML messages.

    Returns a list of message strings (split at TELEGRAM_MAX_LENGTH).
    """
    if date_str is None:
        tz = ZoneInfo(tz_name)
        date_str = datetime.now(tz).strftime("%Y-%m-%d")

    if not events:
        return [f"<b>Winter Daily Digest</b> — {date_str}\n\n今天 Winter 沒有公開更新 ❄️"]

    # Sort events by category priority, then by earliest_time
    events.sort(key=lambda e: (e.category.sort_order, e.earliest_time or datetime.min.replace(tzinfo=timezone.utc)))

    lines: list[str] = []
    lines.append(f"<b>Winter Daily Digest</b> — {date_str}\n")

    current_category: EventCategory | None = None
    tweet_count = 0

    for event in events:
        # Category header
        if event.category != current_category:
            current_category = event.category
            lines.append(f"\n{current_category.emoji} <b>{current_category.value}</b>")

        # Event entry
        lines.append(f"\n• <b>{_escape_html(event.name)}</b>")
        if event.summary:
            lines.append(f"  {_escape_html(event.summary)}")

        # Source links
        if event.tweet_urls:
            links = " ".join(
                f'<a href="{url}">[{i+1}]</a>'
                for i, url in enumerate(event.tweet_urls[:5])
            )
            lines.append(f"  來源：{links}")

        tweet_count += len(event.tweet_ids)

    # Footer
    lines.append(f"\n\n📊 共 {len(events)} 個事件，{tweet_count} 則推文")

    full_text = "\n".join(lines)
    return _split_message(full_text)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _split_message(text: str) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return [text]

    messages = []
    while text:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            messages.append(text)
            break

        # Find a good split point (newline before the limit)
        split_at = text.rfind("\n", 0, TELEGRAM_MAX_LENGTH)
        if split_at == -1:
            split_at = TELEGRAM_MAX_LENGTH

        messages.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return messages
