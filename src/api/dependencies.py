"""FastAPI dependency helpers shared by v1 routers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from src.core.config import Settings, settings
from src.core.db import SessionFactory, health_check


async def get_db_session() -> AsyncGenerator[Session, None]:
    """Yield a database session for request handlers."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def get_settings() -> Settings:
    """Return application settings for request handlers."""
    return settings


async def check_database_health() -> bool:
    """Return whether the configured database is currently reachable."""
    return health_check()
