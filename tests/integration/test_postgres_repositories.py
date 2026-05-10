"""PostgreSQL integration tests for repository queries.

These tests require a disposable PostgreSQL database and are skipped by default.
Run with:

    POSTGRES_TEST_DATABASE_URL=postgresql://... pytest tests/integration
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from src.core.constants import (
    AccountingPrinciples,
    BusinessYearEnd,
    LiquidityScore,
    PipelineStatus,
    RatingGrade,
)
from src.models.orm import Company, UploadAudit
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.repository import (
    CompanyRepository,
    CompareCompaniesNotFoundError,
    SnapshotRepository,
    UploadRepository,
)


@pytest.fixture(scope="module")
def postgres_engine():
    """Return a PostgreSQL engine after applying Alembic migrations."""
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine):
    """Return a session whose test data is rolled back after each test."""
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_repositories_on_postgres(postgres_session, tmp_path):
    """Exercise repository filtering, stats, compare errors, and file safety."""
    baseline_stats = UploadRepository(postgres_session, tmp_path).get_stats()
    ids = _seed_postgres_repository_data(postgres_session, tmp_path)

    company_repo = CompanyRepository(postgres_session)
    snapshot_repo = SnapshotRepository(postgres_session)
    upload_repo = UploadRepository(postgres_session, tmp_path)

    company = company_repo.get_company(ids["company_a"])
    assert company is not None
    assert company.corporate_sector == "Utilities"

    snapshots = snapshot_repo.list_snapshots(
        sector="Utilities",
        country="France",
        currency="EUR",
        limit=10,
    )
    assert [snapshot.version_number for snapshot in snapshots] == [1, 2]

    latest = snapshot_repo.get_latest_for_each_company()
    assert {snapshot.company_id for snapshot in latest} >= {
        ids["company_a"],
        ids["company_b"],
    }

    as_of = snapshot_repo.get_as_of(ids["company_a"], date(2024, 1, 1))
    assert as_of is not None
    assert as_of.version_number == 1

    with pytest.raises(CompareCompaniesNotFoundError):
        company_repo.compare_companies([ids["company_a"], -999_999], date(2024, 1, 2))

    stats = upload_repo.get_stats()
    assert stats.successful - baseline_stats.successful == 2
    assert stats.failed - baseline_stats.failed == 1
    assert stats.duplicates_skipped - baseline_stats.duplicates_skipped == 1
    assert stats.skipped - baseline_stats.skipped == 1

    assert upload_repo.get_source_file_path(ids["safe_upload"]) == tmp_path / "safe.xlsm"
    assert upload_repo.get_source_file_path(ids["unsafe_upload"]) is None


def _seed_postgres_repository_data(session: Session, data_dir: Path) -> dict[str, int]:
    """Insert a small repository fixture and return important primary keys."""
    suffix = uuid4().hex
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    (data_dir / "safe.xlsm").write_bytes(b"stub")

    safe_upload = UploadAudit(
        filename="safe.xlsm",
        file_hash=f"{suffix}a",
        status=PipelineStatus.SUCCESS,
        processed_at=now,
        record_count=4,
    )
    second_upload = UploadAudit(
        filename="second.xlsm",
        file_hash=f"{suffix}b",
        status=PipelineStatus.SUCCESS,
        processed_at=now + timedelta(days=1),
        record_count=5,
    )
    failed_upload = UploadAudit(
        filename="bad.xlsm",
        file_hash=f"{suffix}c",
        status=PipelineStatus.FAILED,
        processed_at=now,
    )
    duplicate_upload = UploadAudit(
        filename="dup.xlsm",
        file_hash=f"{suffix}d",
        status=PipelineStatus.DUPLICATE,
        processed_at=now,
    )
    unsafe_upload = UploadAudit(
        filename="../outside.xlsm",
        file_hash=f"{suffix}e",
        status=PipelineStatus.SKIPPED,
        processed_at=now,
    )
    session.add_all(
        [safe_upload, second_upload, failed_upload, duplicate_upload, unsafe_upload]
    )
    session.flush()

    company_a = Company(
        rated_entity=f"Company A {suffix}",
        corporate_sector="Utilities",
        country_of_origin="France",
    )
    company_b = Company(
        rated_entity=f"Company B {suffix}",
        corporate_sector="Automobiles & Parts",
        country_of_origin="Germany",
    )
    session.add_all([company_a, company_b])
    session.flush()

    session.add_all(
        [
            _make_snapshot(
                company_a.id,
                safe_upload.id,
                version_number=1,
                valid_from=now,
                valid_to=now + timedelta(days=1),
                is_current=False,
                currency="EUR",
            ),
            _make_snapshot(
                company_a.id,
                second_upload.id,
                version_number=2,
                valid_from=now + timedelta(days=1),
                valid_to=None,
                is_current=True,
                currency="EUR",
            ),
            _make_snapshot(
                company_b.id,
                safe_upload.id,
                version_number=1,
                valid_from=now,
                valid_to=None,
                is_current=True,
                currency="USD",
            ),
        ]
    )
    session.flush()
    return {
        "company_a": company_a.id,
        "company_b": company_b.id,
        "safe_upload": safe_upload.id,
        "unsafe_upload": unsafe_upload.id,
    }


def _make_snapshot(
    company_id: int,
    upload_id: int,
    *,
    version_number: int,
    valid_from: datetime,
    valid_to: datetime | None,
    is_current: bool,
    currency: str,
) -> OrmSnapshot:
    """Build a complete CompanySnapshot ORM object for integration tests."""
    return OrmSnapshot(
        company_id=company_id,
        upload_id=upload_id,
        version_number=version_number,
        snapshot_date=valid_from.date(),
        valid_from=valid_from,
        valid_to=valid_to,
        is_current=is_current,
        reporting_currency=currency,
        accounting_principles=AccountingPrinciples.IFRS,
        business_year_end=BusinessYearEnd.DECEMBER,
        segmentation_criteria=None,
        business_risk_profile=RatingGrade.A,
        blended_industry_risk_profile=RatingGrade.A,
        competitive_positioning=RatingGrade.A,
        market_share=RatingGrade.A,
        diversification=RatingGrade.A,
        operating_profitability=RatingGrade.A,
        sector_specific_factor_1=None,
        sector_specific_factor_2=None,
        financial_risk_profile=RatingGrade.BBB,
        leverage=RatingGrade.BBB,
        interest_cover=RatingGrade.BBB,
        cash_flow_cover=RatingGrade.BBB,
        liquidity=LiquidityScore.ADEQUATE,
    )
