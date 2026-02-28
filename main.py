#!/usr/bin/env python3
"""Winter Daily Digest — CLI entry point."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import traceback
from datetime import timezone
from zoneinfo import ZoneInfo

from src.config import load_config
from src.grouping.clusterer import group_tweets
from src.storage.accounts import (
    load_accounts,
    mark_discovery_done,
    needs_rediscovery,
    save_accounts,
)
from src.storage.cache import TweetCache
from src.telegram.formatter import format_digest
from src.telegram.sender import send_digest, send_error_notification
from src.twitter.client import TwitterClient
from src.twitter.collector import collect_tweets
from src.twitter.discovery import discover_accounts


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Winter Daily Digest")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "discover"],
                        help="Command to execute (default: run)")
    parser.add_argument("--dry-run", action="store_true", help="Print digest instead of sending to Telegram")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    return parser.parse_args()


async def run_discover(config) -> None:
    """Run account discovery only."""
    logger = logging.getLogger("discover")
    client = TwitterClient(rapidapi_key=config.rapidapi_key)

    try:
        accounts = await discover_accounts(
            client=client,
            keywords=config.discovery.keywords,
            min_followers=config.discovery.min_followers,
            min_winter_ratio=config.discovery.min_winter_ratio,
            max_accounts=config.discovery.max_accounts,
            seed_accounts=config.manual_include,
        )

        # Apply manual exclusions
        excluded = set(s.lower() for s in config.manual_exclude)
        accounts = [a for a in accounts if a.username.lower() not in excluded]

        save_accounts(accounts, str(config.data_dir / "accounts.json"))
        mark_discovery_done(str(config.data_dir / "last_discovery.txt"))

        logger.info("Discovery complete: %d accounts", len(accounts))
        for a in accounts:
            logger.info("  @%-20s  %-10s  %d followers  %.0f%% winter",
                         a.username, a.account_type.value, a.followers, a.winter_ratio * 100)
    finally:
        await client.close()


async def run_digest(config, dry_run: bool = False) -> None:
    """Full pipeline: collect → group → format → send."""
    logger = logging.getLogger("digest")
    tz = ZoneInfo(config.timezone)

    client = TwitterClient(rapidapi_key=config.rapidapi_key)

    try:
        # Check if rediscovery is needed
        if needs_rediscovery(
            str(config.data_dir / "last_discovery.txt"),
            config.discovery.rescan_interval_days,
        ):
            logger.info("Account rediscovery needed, running discovery...")
            await _run_discover_with_client(config, client)

        # Load tracked accounts
        accounts = load_accounts(str(config.data_dir / "accounts.json"))
        if not accounts:
            logger.warning("No tracked accounts found. Running discovery first...")
            await _run_discover_with_client(config, client)
            accounts = load_accounts(str(config.data_dir / "accounts.json"))

        if not accounts:
            logger.error("Still no accounts after discovery. Check config and API key.")
            return

        # Collect tweets
        cache = TweetCache(str(config.data_dir / "cache.db"))
        try:
            tweets = await collect_tweets(
                client=client,
                accounts=accounts,
                cache=cache,
                hours=24,
                tz=timezone.utc,
            )
        finally:
            cache.cleanup(days=30)
            cache.close()

        logger.info("Collected %d tweets", len(tweets))

        # Group tweets into events
        events = await group_tweets(tweets=tweets)
        logger.info("Grouped into %d events", len(events))

        # Format digest
        messages = format_digest(events, tz_name=config.timezone)

        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN — Telegram message preview:")
            print("=" * 60)
            for i, msg in enumerate(messages):
                if i > 0:
                    print("-" * 40)
                print(msg)
            print("=" * 60)
            print(f"({len(messages)} message(s), {sum(len(m) for m in messages)} chars total)")
        else:
            await send_digest(
                messages=messages,
                bot_token=config.telegram.bot_token,
                chat_id=config.telegram.chat_id,
            )
            logger.info("Digest sent to Telegram!")
    finally:
        await client.close()


async def _run_discover_with_client(config, client: TwitterClient) -> None:
    """Run discovery using an existing client (avoids creating a second one)."""
    logger = logging.getLogger("discover")

    accounts = await discover_accounts(
        client=client,
        keywords=config.discovery.keywords,
        min_followers=config.discovery.min_followers,
        min_winter_ratio=config.discovery.min_winter_ratio,
        max_accounts=config.discovery.max_accounts,
        seed_accounts=config.manual_include,
    )

    excluded = set(s.lower() for s in config.manual_exclude)
    accounts = [a for a in accounts if a.username.lower() not in excluded]

    save_accounts(accounts, str(config.data_dir / "accounts.json"))
    mark_discovery_done(str(config.data_dir / "last_discovery.txt"))
    logger.info("Discovery complete: %d accounts", len(accounts))


async def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        sys.exit(1)

    try:
        if args.command == "discover":
            await run_discover(config)
        else:
            await run_digest(config, dry_run=args.dry_run)
    except Exception as e:
        logger.exception("Fatal error")
        # Try to send error notification to Telegram
        try:
            tb = traceback.format_exc()
            await send_error_notification(
                error_message=f"{type(e).__name__}: {e}\n\n{tb[-500:]}",
                bot_token=config.telegram.bot_token,
                chat_id=config.telegram.chat_id,
            )
        except Exception:
            logger.error("Could not send error notification")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
