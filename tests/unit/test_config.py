"""Unit tests for src.core.config — Settings construction and field validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_postgres_fields_have_defaults():
    """All postgres fields except password have defaults so local dev works without a .env."""
    s = Settings()
    assert s.postgres_host == "localhost"
    assert s.postgres_port == 5432
    assert s.postgres_db == "scope_ratings"
    assert s.postgres_user == "scope"


def test_database_url_is_computed_from_parts():
    """database_url must be assembled from the individual postgres fields."""
    s = Settings()
    assert s.database_url == (
        f"postgresql://{s.postgres_user}:{s.postgres_password}"
        f"@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    )


def test_database_url_reflects_overridden_parts(monkeypatch):
    """Changing individual parts must change the computed URL."""
    monkeypatch.setenv("POSTGRES_HOST", "db.prod.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    s = Settings()
    assert "db.prod.internal:5433" in s.database_url


def test_sqlalchemy_pool_settings_have_defaults():
    """SQLAlchemy engine pool settings must have production-safe defaults."""
    s = Settings()
    assert s.sqlalchemy_pool_size == 5
    assert s.sqlalchemy_max_overflow == 10
    assert s.sqlalchemy_pool_timeout == 30
    assert s.sqlalchemy_pool_recycle == 1800


def test_sqlalchemy_pool_settings_read_from_env(monkeypatch):
    """Pool settings must be configurable from environment variables."""
    monkeypatch.setenv("SQLALCHEMY_POOL_SIZE", "7")
    monkeypatch.setenv("SQLALCHEMY_MAX_OVERFLOW", "3")
    monkeypatch.setenv("SQLALCHEMY_POOL_TIMEOUT", "12")
    monkeypatch.setenv("SQLALCHEMY_POOL_RECYCLE", "900")
    s = Settings()
    assert s.sqlalchemy_pool_size == 7
    assert s.sqlalchemy_max_overflow == 3
    assert s.sqlalchemy_pool_timeout == 12
    assert s.sqlalchemy_pool_recycle == 900


def test_postgres_password_is_required(monkeypatch):
    """Missing POSTGRES_PASSWORD must raise at Settings() construction time."""
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reads_postgres_password_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret123")
    s = Settings()
    assert s.postgres_password == "secret123"


def test_app_settings_defaults():
    """log_level, data_dir, and environment must all have sensible out-of-the-box defaults."""
    s = Settings()
    assert s.log_level == "INFO"
    assert s.data_dir == Path("./data")
    assert s.environment == "development"


def test_settings_reads_log_level_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.log_level == "DEBUG"


def test_settings_reads_data_dir_from_env(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
    s = Settings()
    assert s.data_dir == Path("/tmp/test_data")


def test_environment_accepts_valid_values(monkeypatch):
    for env in ("development", "staging", "production"):
        monkeypatch.setenv("ENVIRONMENT", env)
        s = Settings()
        assert s.environment == env


def test_environment_rejects_invalid_value(monkeypatch):
    """An unrecognised environment string must fail validation immediately."""
    monkeypatch.setenv("ENVIRONMENT", "prod")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
