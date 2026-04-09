from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HomeGroup"
    env: str = "development"
    debug: bool = True
    database_url: str = "sqlite+pysqlite:///./homegroup.db"

    model_config = SettingsConfigDict(
        env_prefix="HOMEGROUP_",
        env_file=".env",
        extra="ignore",
    )

