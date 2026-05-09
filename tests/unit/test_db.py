"""Unit tests for src.core.db — engine, session factory, and session lifecycle."""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from src.core.db import Base, SessionFactory, engine, get_session


def test_engine_is_sqlalchemy_engine():
    assert isinstance(engine, Engine)


def test_engine_dialect_is_postgresql():
    """
    Checks that the engine is configured for PostgreSQL specifically. 
    This catches mistakes like accidentally using SQLite.
    """
    assert engine.dialect.name == "postgresql"


def test_session_factory_creates_session():
    session = SessionFactory()
    assert isinstance(session, Session)
    session.close()


def test_base_is_declarative_base():
    assert issubclass(Base, DeclarativeBase)


def test_get_session_success_path():
    """On a clean exit the session must be yielded, committed, and closed."""
    mock_session = MagicMock(spec=Session)
    with patch("src.core.db.SessionFactory", return_value=mock_session):
        with get_session() as session:
            assert session is mock_session
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


def test_get_session_error_path():
    """On exception the session must be rolled back (not committed) and still closed."""
    mock_session = MagicMock(spec=Session)
    with patch("src.core.db.SessionFactory", return_value=mock_session):
        with pytest.raises(RuntimeError):
            with get_session():
                raise RuntimeError("simulated error")
    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()
