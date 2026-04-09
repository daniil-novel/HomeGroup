from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from homegroup.infrastructure.config import Settings, get_settings


def create_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    active_settings = settings or get_settings()
    engine = create_engine(active_settings.database_url, future=True, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


SessionFactory = create_session_factory()


def get_db_session() -> Generator[Session, None, None]:
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()

