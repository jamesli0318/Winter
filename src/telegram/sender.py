from __future__ import annotations

import logging

import telegram

logger = logging.getLogger(__name__)


async def send_digest(
    messages: list[str],
    bot_token: str,
    chat_id: str,
) -> None:
    """Send formatted digest messages to Telegram."""
    bot = telegram.Bot(token=bot_token)

    for i, msg in enumerate(messages):
        for attempt in range(2):
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
                if attempt == 0:
                    logger.warning("Telegram send failed, retrying once")
                else:
                    logger.exception("Telegram send failed for message %d", i + 1)
                    raise


async def send_error_notification(
    error_message: str,
    bot_token: str,
    chat_id: str,
) -> None:
    """Send an error notification to Telegram."""
    bot = telegram.Bot(token=bot_token)
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
