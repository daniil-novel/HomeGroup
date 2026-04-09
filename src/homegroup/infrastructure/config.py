from __future__ import annotations

from datetime import time
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from homegroup.domain.enums import SummaryMode


class Settings(BaseSettings):
    app_name: str = "HomeGroup"
    env: str = "development"
    debug: bool = True
    base_url: str = "http://localhost:8000"
    webhook_secret: str = "dev-secret"
    domain: str = "localhost"
    database_url: str = "sqlite+pysqlite:///./homegroup.db"
    timezone: str = "Europe/Moscow"
    morning_time: time = time(hour=7, minute=0)
    evening_time: time = time(hour=18, minute=0)
    weekly_review_day: str = "SUN"
    weekly_review_time: time = time(hour=11, minute=0)
    purchase_confirmation_threshold: Decimal = Decimal("15000")
    archive_retention_days: int = 180
    backup_dir: Path = Path("./backups")
    backup_passphrase: str = "change-me"
    bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_owner_phone: str = ""
    telegram_second_user_id: int = 0
    telegram_second_user_username: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash-lite"
    summary_mode: SummaryMode = SummaryMode.STANDARD
    mini_app_secret: str = "mini-app-dev-secret"
    quiet_hours_start: time = time(hour=23, minute=0)
    quiet_hours_end: time = time(hour=7, minute=0)

    model_config = SettingsConfigDict(
        env_prefix="HOMEGROUP_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def webhook_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/telegram/webhook"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    return settings
