"""PostgreSQL/Alembic integration checks for production-only constraints.

These tests are skipped by default because they require a disposable
PostgreSQL database.  Run with:

    POSTGRES_TEST_DATABASE_URL=postgresql+psycopg://... pytest tests/integration
"""

from __future__ import annotations

import os

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


@pytest.mark.integration
def test_alembic_head_creates_postgres_constraints():
    """Apply migrations to PostgreSQL and inspect idempotency/SCD indexes."""
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        audit_indexes = {idx["name"] for idx in inspector.get_indexes("upload_audit")}
        company_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("company")
        }
        snapshot_indexes = {
            idx["name"] for idx in inspector.get_indexes("company_snapshot")
        }
    finally:
        engine.dispose()

    assert "ix_upload_audit_success_file_hash" in audit_indexes
    assert "ix_company_snapshot_one_current_per_company" in snapshot_indexes
    assert "uq_company_identity" in company_constraints
