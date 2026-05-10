"""End-to-end tests: real Excel files -> pipeline -> API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from alembic import command
from src.api.dependencies import check_database_health, get_db_session, get_settings
from src.api.main import create_app
from src.core.db import Base
from src.pipeline.pipeline import Pipeline


@pytest.mark.asyncio
async def test_real_workbooks_load_and_serve_through_api_on_sqlite(tmp_path):
    """Fast local E2E smoke test using SQLite instead of production PostgreSQL."""
    data_dir = tmp_path / "data"
    report_dir = tmp_path / "reports"
    data_dir.mkdir()
    _copy_sample_workbooks(data_dir)

    engine = create_engine(f"sqlite:///{tmp_path / 'e2e.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_company_snapshot_one_current_per_company"))
        conn.commit()

    try:
        with Session(engine) as session:
            report = Pipeline(session).process_directory_report(data_dir, report_dir=report_dir)

        assert report.files_found == 4
        assert report.succeeded == 4
        assert report.failed == 0
        assert report.validation_error_count == 0
        assert report.records_written == 255
        assert len(list(report_dir.glob("data_quality_report_*.json"))) == 1

        app = _make_test_app(engine, data_dir)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await _assert_api_surfaces_loaded_workbooks(client)
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_workbooks_load_and_serve_through_api_on_postgres(tmp_path):
    """Production-equivalent E2E: Alembic schema on PostgreSQL plus API reads."""
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")

    data_dir = tmp_path / "data"
    report_dir = tmp_path / "reports"
    data_dir.mkdir()
    _copy_sample_workbooks(data_dir)

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    _clean_database(engine)
    try:
        with Session(engine) as session:
            report = Pipeline(session).process_directory_report(data_dir, report_dir=report_dir)

        assert report.files_found == 4
        assert report.succeeded == 4
        assert report.failed == 0
        assert report.validation_error_count == 0
        assert report.records_written == 255
        assert len(list(report_dir.glob("data_quality_report_*.json"))) == 1

        app = _make_test_app(engine, data_dir)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await _assert_api_surfaces_loaded_workbooks(client)
    finally:
        _clean_database(engine)
        engine.dispose()


async def _assert_api_surfaces_loaded_workbooks(client: httpx.AsyncClient) -> None:
    """Assert the API exposes the real assignment workbook data."""
    health = await client.get("/health")
    assert health.status_code == 200

    companies = await client.get("/v1/companies")
    assert companies.status_code == 200
    company_rows = companies.json()
    companies_by_name = {row["rated_entity"]: row for row in company_rows}
    assert len(companies_by_name) == 2
    assert companies_by_name["Company A"]["corporate_sector"] == "Personal & Household Goods"
    assert companies_by_name["Company A"]["country_of_origin"] == (
        "Federal Republic of Germany"
    )
    assert companies_by_name["Company B"]["corporate_sector"] == "Automobiles & Parts"
    assert companies_by_name["Company B"]["country_of_origin"] == "Swiss Confederation"

    latest = await client.get("/v1/snapshots/latest")
    assert latest.status_code == 200
    latest_rows = latest.json()
    assert len(latest_rows) == 2
    assert {row["version_number"] for row in latest_rows} == {2}
    assert {row["reporting_currency"] for row in latest_rows} == {"EUR", "CHF"}

    uploads = await client.get("/v1/uploads/stats")
    assert uploads.status_code == 200
    assert uploads.json() == {
        "total_uploads": 4,
        "successful": 4,
        "failed": 0,
        "duplicates_skipped": 0,
        "skipped": 0,
        "total_records": 255,
    }

    compare = await client.get(
        "/v1/companies/compare",
        params=[
            ("company_ids", company_rows[0]["id"]),
            ("company_ids", company_rows[1]["id"]),
            ("as_of_date", datetime.now(tz=timezone.utc).date().isoformat()),
        ],
    )
    assert compare.status_code == 200
    compare_payload = compare.json()
    assert len(compare_payload["snapshots"]) == 2
    assert {row["country_of_origin"] for row in compare_payload["snapshots"]} == {
        "Federal Republic of Germany",
        "Swiss Confederation",
    }


def _copy_sample_workbooks(data_dir: Path) -> None:
    """Copy assignment workbook fixtures into a temporary data directory."""
    source_dir = Path("data")
    paths = sorted(source_dir.glob("*.xlsm"))
    assert len(paths) == 4
    for path in paths:
        (data_dir / path.name).write_bytes(path.read_bytes())


def _make_test_app(engine, data_dir: Path):
    """Return a FastAPI app wired to a temporary SQLite warehouse."""
    app = create_app()

    async def override_session():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    async def override_settings():
        return SimpleNamespace(data_dir=data_dir)

    async def override_health():
        return True

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[check_database_health] = override_health
    return app


def _clean_database(engine: Engine) -> None:
    """Remove test rows from all application tables in dependency order."""
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
