from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from src.twitter.models import TrackedAccount

logger = logging.getLogger(__name__)


def save_accounts(accounts: list[TrackedAccount], path: str = "data/accounts.json") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "accounts": [a.to_dict() for a in accounts],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d accounts to %s", len(accounts), path)


def load_accounts(path: str = "data/accounts.json") -> list[TrackedAccount]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    accounts = [TrackedAccount.from_dict(a) for a in data.get("accounts", [])]
    logger.info("Loaded %d accounts from %s", len(accounts), path)
    return accounts


def needs_rediscovery(
    last_discovery_path: str = "data/last_discovery.txt",
    interval_days: int = 7,
) -> bool:
    if not os.path.exists(last_discovery_path):
        return True
    try:
        with open(last_discovery_path) as f:
            ts = f.read().strip()
        last = datetime.fromisoformat(ts)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last).days
        return elapsed >= interval_days
    except (ValueError, OSError):
        return True


def mark_discovery_done(path: str = "data/last_discovery.txt") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())
