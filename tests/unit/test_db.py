"""Unit tests for src.core.db — engine, session factory, and session lifecycle."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from src.core.db import Base, SessionFactory, engine, get_session, session_scope


def test_engine_is_sqlalchemy_engine():
    assert isinstance(engine, Engine)


def test_engine_dialect_is_postgresql():
    """
    Checks that the engine is configured for PostgreSQL specifically.
    This catches mistakes like accidentally using SQLite.
    """
    assert engine.dialect.name == "postgresql"


def test_engine_pool_uses_configured_settings():
    """Engine queue pool must use Settings-derived pool values."""
    from src.core.config import settings

    assert engine.pool.size() == settings.sqlalchemy_pool_size
    assert engine.pool._max_overflow == settings.sqlalchemy_max_overflow
    assert engine.pool._timeout == settings.sqlalchemy_pool_timeout
    assert engine.pool._recycle == settings.sqlalchemy_pool_recycle


def test_session_factory_creates_session():
    session = SessionFactory()
    assert isinstance(session, Session)
    session.close()


def test_base_is_declarative_base():
    assert issubclass(Base, DeclarativeBase)


def test_get_session_is_plain_generator():
    """get_session must be a plain generator — FastAPI Depends() requires this shape."""
    import inspect

    assert inspect.isgeneratorfunction(get_session)


def test_session_scope_success_path():
    """On a clean exit the session must be yielded, committed, and closed."""
    mock_session = MagicMock(spec=Session)
    with patch("src.core.db.SessionFactory", return_value=mock_session):
        with session_scope() as session:
            assert session is mock_session
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


def test_session_scope_error_path():
    """On exception the session must be rolled back (not committed) and still closed."""
    mock_session = MagicMock(spec=Session)
    with patch("src.core.db.SessionFactory", return_value=mock_session):
        with pytest.raises(RuntimeError):
            with session_scope():
                raise RuntimeError("simulated error")
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()
