# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily digest bot for **aespa Winter** Twitter updates, delivered to Telegram. Pipeline: discover accounts → collect tweets via RapidAPI → group into events → format & send to Telegram.

## Commands

```bash
# Install dependencies
pip install -e .

# Run full digest pipeline (collect → group → format → send)
python main.py run

# Dry-run (prints digest to stdout, no Telegram send)
python main.py run --dry-run --verbose

# Account discovery only
python main.py discover --verbose

# Docker
docker compose up -d   # runs on cron: daily 08:00 Taipei time
```

No test suite or linter configured.

## Architecture

```
main.py                         # CLI entry, async orchestration
src/
  config.py                     # AppConfig from config.yaml + .env
  twitter/
    client.py                   # httpx async client → RapidAPI Twttr API (twitter241)
    discovery.py                # Keyword search → classify → winter_ratio filter
    collector.py                # Fetch timelines, dedup via SQLite cache
    models.py                   # TrackedAccount, RawTweet, AccountType enum
  grouping/
    clusterer.py                # Entry point for tweet grouping
    algorithm.py                # Rule-based algorithmic clustering
    models.py                   # Event, EventCategory enum
  storage/
    cache.py                    # SQLite tweet dedup (30-day retention)
    accounts.py                 # JSON persistence for discovered accounts
  telegram/
    formatter.py                # HTML formatting, 4096-char message splitting
    sender.py                   # Telegram bot send with exponential backoff (4 retries)
```

### Data Flow

1. **Discovery** (`discovery.py`): Search RapidAPI for Winter-related accounts by keywords, classify by bio regex (official/fansite/translator/news), compute winter_ratio from tweet samples, filter & persist to `data/accounts.json`
2. **Collection** (`collector.py`): Fetch timelines for tracked accounts, skip retweets, filter by 24h window, **all accounts** filtered by Winter keywords (`winter|윈터|ウィンター|민정|minjeong|김민정`), dedup via SQLite cache
3. **Grouping** (`clusterer.py` → `algorithm.py`): Rule-based clustering groups tweets into Event objects categorized as 行程/媒體/SNS/新聞
4. **Delivery** (`formatter.py` → `sender.py`): Format events as Telegram HTML, split at 4096 chars, send via bot API

### Key Patterns

- **Fully async**: all I/O via asyncio (httpx, telegram-bot)
- **Rate limiting**: exponential backoff on 429s, sequential delays between accounts (2s) and searches (3s)
- **Rediscovery**: auto-triggers every 7 days (configurable), checks `data/last_discovery.txt`
- **Manual overrides**: `manual_include` seeds always added, `manual_exclude` always removed

## Configuration

Two env vars required in `.env`: `TELEGRAM_BOT_TOKEN`, `RAPIDAPI_KEY`

`config.yaml` structure (see `config.example.yaml`):
- `discovery`: keywords, min_followers, min_winter_ratio, max_accounts, rescan_interval_days
- `telegram.chat_id`, `timezone`
- `manual_include` / `manual_exclude`: override discovery results

Runtime data stored in `data/`: `accounts.json`, `cache.db`, `last_discovery.txt`

## RapidAPI Endpoints (Twttr API — twitter241)

| Method | Endpoint | Params |
|--------|----------|--------|
| `get_user_profile` | `/user` | `username` |
| `get_timeline` | `/user-tweets` | `user` (rest_id), `count` |
| `search_users` | `/search` | `query`, `type=People`, `count` |

Responses are GraphQL format; `client.py` flattens them into legacy-compatible dicts with fields: `screen_name`, `sub_count` (followers), `desc` (bio), `favorites` (likes), `retweets`, `tweet_id`, `text`, `created_at`, `media.photo`/`media.video`
