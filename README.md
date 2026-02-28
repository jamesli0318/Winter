# Winter Daily Digest

Automated daily digest of **aespa Winter** Twitter updates, delivered to Telegram.

Discovers fan/official accounts via RapidAPI, collects recent tweets, filters for Winter-relevant content, groups them into events, and sends a formatted digest to your Telegram chat every morning.

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env        # fill in your API keys
cp config.example.yaml config.yaml  # set your Telegram chat_id

docker compose up -d        # runs daily at 08:00 Taipei time
```

### Local

```bash
pip install -e .

# Run full pipeline
python main.py run

# Dry-run (preview without sending)
python main.py run --dry-run --verbose

# Account discovery only
python main.py discover --verbose
```

## Configuration

### Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token from [@BotFather](https://t.me/BotFather) |
| `RAPIDAPI_KEY` | RapidAPI key with [Twttr API](https://rapidapi.com/davethebeast/api/twitter241) subscription |

### Config File (`config.yaml`)

```yaml
discovery:
  keywords:              # search terms for account discovery
    - "Winter aespa"
    - "윈터 에스파"
  min_followers: 500     # minimum follower count
  min_winter_ratio: 0.25 # minimum ratio of Winter-related tweets
  max_accounts: 25
  rescan_interval_days: 7

telegram:
  chat_id: "your_chat_id"

timezone: "Asia/Taipei"

manual_include:          # always track these accounts
  - "aespa_official"
manual_exclude: []       # never track these accounts
```

## How It Works

```
Discover accounts → Collect tweets → Filter → Group → Send to Telegram
```

1. **Discovery** - Searches Twitter for Winter-related accounts by keywords, classifies them (official/fansite/translator/news), and filters by Winter tweet ratio
2. **Collection** - Fetches timelines for tracked accounts within the past 24 hours, skipping retweets
3. **Filtering** - All tweets must match Winter keywords (`winter|윈터|ウィンター|민정|minjeong|김민정`)
4. **Grouping** - Rule-based clustering organizes tweets into events (行程/媒體/SNS/新聞)
5. **Delivery** - Formats events as Telegram HTML and sends via bot API

## Project Structure

```
main.py                 # CLI entry point
src/
  config.py             # Config from config.yaml + .env
  twitter/
    client.py           # RapidAPI Twttr API (twitter241) client
    discovery.py        # Account discovery & classification
    collector.py        # Tweet collection & filtering
    models.py           # Data models
  grouping/
    clusterer.py        # Grouping entry point
    algorithm.py        # Rule-based clustering
    models.py           # Event models
  storage/
    cache.py            # SQLite tweet dedup (30-day retention)
    accounts.py         # Account persistence
  telegram/
    formatter.py        # HTML formatting & message splitting
    sender.py           # Telegram send with retries
data/                   # Runtime data (gitignored)
  accounts.json         # Discovered accounts
  cache.db              # Tweet dedup cache
```

## License

MIT
