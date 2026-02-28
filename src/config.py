from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class AccountEntry:
    username: str
    type: str  # "official", "fansite", "translator", "news", "other"


@dataclass
class DiscoveryConfig:
    keywords: list[str] = field(default_factory=lambda: ["Winter aespa", "윈터 에스파"])
    min_followers: int = 500
    min_winter_ratio: float = 0.25
    max_accounts: int = 25
    rescan_interval_days: int = 7


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass
class AppConfig:
    rapidapi_key: str
    telegram: TelegramConfig
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    manual_include: list[str] = field(default_factory=list)
    manual_exclude: list[str] = field(default_factory=list)
    timezone: str = "Asia/Taipei"
    data_dir: Path = field(default_factory=lambda: Path("data"))


def load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig:
    load_dotenv(env_path)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    rapidapi_key = os.environ.get("RAPIDAPI_KEY", "")

    if not telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment or .env")
    if not rapidapi_key:
        raise ValueError("RAPIDAPI_KEY not set in environment or .env")

    tg = raw.get("telegram", {})
    disc_cfg = raw.get("discovery", {})

    default_keywords = ["Winter aespa", "윈터 에스파"]
    discovery = DiscoveryConfig(
        keywords=disc_cfg.get("keywords", default_keywords),
        min_followers=disc_cfg.get("min_followers", 500),
        min_winter_ratio=disc_cfg.get("min_winter_ratio", 0.25),
        max_accounts=disc_cfg.get("max_accounts", 25),
        rescan_interval_days=disc_cfg.get("rescan_interval_days", 7),
    )

    return AppConfig(
        rapidapi_key=rapidapi_key,
        telegram=TelegramConfig(
            bot_token=telegram_token,
            chat_id=str(tg["chat_id"]),
        ),
        discovery=discovery,
        manual_include=raw.get("manual_include", []),
        manual_exclude=raw.get("manual_exclude", []),
        timezone=raw.get("timezone", "Asia/Taipei"),
    )
