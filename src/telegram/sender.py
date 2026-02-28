from __future__ import annotations

import asyncio
import logging

import telegram
from telegram.request import HTTPXRequest

logger = logging.getLogger(__name__)

SEND_RETRIES = 4
RETRY_DELAYS = [3, 5, 10]


def _make_bot(bot_token: str) -> telegram.Bot:
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    return telegram.Bot(token=bot_token, request=request)


async def send_digest(
    messages: list[str],
    bot_token: str,
    chat_id: str,
) -> None:
    """Send formatted digest messages to Telegram."""
    bot = _make_bot(bot_token)

    for i, msg in enumerate(messages):
        for attempt in range(SEND_RETRIES):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                logger.info("Sent message %d/%d to Telegram", i + 1, len(messages))
                break
            except Exception:
                if attempt < SEND_RETRIES - 1:
                    wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.warning(
                        "Telegram send failed (attempt %d/%d), retrying in %ds",
                        attempt + 1, SEND_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.exception("Telegram send failed for message %d", i + 1)
                    raise


async def send_error_notification(
    error_message: str,
    bot_token: str,
    chat_id: str,
) -> None:
    """Send an error notification to Telegram."""
    bot = _make_bot(bot_token)
    text = f"⚠️ <b>Winter Digest Error</b>\n\n<pre>{_escape_html(error_message[:3000])}</pre>"
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Failed to send error notification to Telegram")


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
