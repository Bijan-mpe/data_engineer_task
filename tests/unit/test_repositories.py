"""Unit tests for repository classes using an in-memory SQLite database."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.core.constants import (
    AccountingPrinciples,
    BusinessYearEnd,
    LiquidityScore,
    PipelineStatus,
    RatingGrade,
)
from src.core.db import Base
from src.models.orm import (
    Company,
    IndustrySegment,
    RatingMethodology,
    ScopeMetric,
    UploadAudit,
)
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.repository import (
    CompanyRepository,
    CompareCompaniesNotFoundError,
    SnapshotRepository,
    UploadRepository,
)
from src.repository.pagination import MAX_PAGE_LIMIT


@pytest.fixture(scope="module")
def sqlite_engine():
    """SQLite schema for repository tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_company_snapshot_one_current_per_company"))
        conn.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    """Return an isolated SQLAlchemy session with sample warehouse rows."""
    session = Session(sqlite_engine)
    _seed_repository_data(session)
    yield session
    session.close()
    with sqlite_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def company_repo(db_session):
    """CompanyRepository fixture."""
    return CompanyRepository(db_session)


@pytest.fixture
def snapshot_repo(db_session):
    """SnapshotRepository fixture."""
    return SnapshotRepository(db_session)


@pytest.fixture
def upload_repo(db_session, tmp_path):
    """UploadRepository fixture with a data directory."""
    (tmp_path / "a_v1.xlsm").write_bytes(b"stub")
    return UploadRepository(db_session, tmp_path)


def _seed_repository_data(session: Session) -> None:
    """Insert deterministic companies, snapshots, child rows, and uploads."""
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    upload_a = UploadAudit(
        filename="a_v1.xlsm",
        file_hash="a" * 64,
        status=PipelineStatus.SUCCESS,
        processed_at=now,
        record_count=4,
    )
    upload_a2 = UploadAudit(
        filename="a_v2.xlsm",
        file_hash="b" * 64,
        status=PipelineStatus.SUCCESS,
        processed_at=now + timedelta(days=1),
        record_count=5,
    )
    upload_failed = UploadAudit(
        filename="bad.xlsm",
        file_hash="c" * 64,
        status=PipelineStatus.FAILED,
        error_message="bad file",
        processed_at=now,
    )
    upload_duplicate = UploadAudit(
        filename="dup.xlsm",
        file_hash="a" * 64,
        status=PipelineStatus.DUPLICATE,
        processed_at=now,
    )
    upload_skipped = UploadAudit(
        filename="../secret.xlsm",
        file_hash="d" * 64,
        status=PipelineStatus.SKIPPED,
        processed_at=now,
    )
    session.add_all([upload_a, upload_a2, upload_failed, upload_duplicate, upload_skipped])
    session.flush()

    company_a = Company(
        rated_entity="Company A",
        corporate_sector="Utilities",
        country_of_origin="France",
    )
    company_b = Company(
        rated_entity="Company B",
        corporate_sector="Automobiles & Parts",
        country_of_origin="Germany",
    )
    session.add_all([company_a, company_b])
    session.flush()

    snap_a1 = _make_snapshot(
        company_a.id,
        upload_a.id,
        version_number=1,
        valid_from=now,
        valid_to=now + timedelta(days=1),
        is_current=False,
        currency="EUR",
    )
    snap_a2 = _make_snapshot(
        company_a.id,
        upload_a2.id,
        version_number=2,
        valid_from=now + timedelta(days=1),
        valid_to=None,
        is_current=True,
        currency="EUR",
    )
    snap_b1 = _make_snapshot(
        company_b.id,
        upload_a.id,
        version_number=1,
        valid_from=now,
        valid_to=None,
        is_current=True,
        currency="USD",
    )
    session.add_all([snap_a1, snap_a2, snap_b1])
    session.flush()

    session.add_all(
        [
            IndustrySegment(
                snapshot_id=snap_a2.id,
                position=1,
                industry_name="Utilities",
                risk_score="A",
                weight=1.0,
            ),
            RatingMethodology(
                snapshot_id=snap_a2.id,
                position=1,
                methodology_name="General Corporate Rating Methodology",
            ),
            ScopeMetric(
                snapshot_id=snap_a2.id,
                metric_name="Scope-adjusted debt/EBITDA",
                year=2024,
                is_estimate=False,
                value=2.5,
            ),
        ]
    )
    session.commit()


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
    """Build a minimally complete CompanySnapshot ORM object."""
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


class TestCompanyRepository:
    """Company repository behavior."""

    def test_list_companies_ordered_by_name(self, company_repo):
        companies = company_repo.list_companies()
        assert [c.rated_entity for c in companies] == ["Company A", "Company B"]

    def test_list_companies_supports_pagination(self, company_repo):
        companies = company_repo.list_companies(limit=1, offset=1)
        assert [c.rated_entity for c in companies] == ["Company B"]

    @pytest.mark.parametrize(
        ("limit", "offset"),
        [(0, 0), (-1, 0), (MAX_PAGE_LIMIT + 1, 0), (1, -1)],
    )
    def test_list_companies_rejects_invalid_pagination(
        self, company_repo, limit, offset
    ):
        with pytest.raises(ValueError):
            company_repo.list_companies(limit=limit, offset=offset)

    def test_get_company_returns_match(self, company_repo):
        company = company_repo.get_company(1)
        assert company is not None
        assert company.rated_entity == "Company A"

    def test_get_company_missing_returns_none(self, company_repo):
        assert company_repo.get_company(999) is None

    def test_get_versions_returns_version_order(self, company_repo):
        versions = company_repo.get_versions(1)
        assert [snapshot.version_number for snapshot in versions] == [1, 2]

    def test_get_history_returns_chronological_snapshots(self, company_repo):
        history = company_repo.get_history(1)
        assert [snapshot.version_number for snapshot in history] == [1, 2]

    def test_compare_companies_returns_as_of_snapshots(self, company_repo):
        snapshots = company_repo.compare_companies([1, 2], date(2024, 1, 2))
        assert [snapshot.company.rated_entity for snapshot in snapshots] == [
            "Company A",
            "Company B",
        ]
        assert [snapshot.version_number for snapshot in snapshots] == [2, 1]

    def test_compare_companies_raises_for_missing_requested_id(self, company_repo):
        with pytest.raises(CompareCompaniesNotFoundError) as exc_info:
            company_repo.compare_companies([1, 999], date(2024, 1, 2))
        assert exc_info.value.missing_company_ids == [999]

    def test_compare_companies_can_ignore_missing_requested_id(self, company_repo):
        snapshots = company_repo.compare_companies(
            [1, 999],
            date(2024, 1, 2),
            require_all=False,
        )
        assert [snapshot.company_id for snapshot in snapshots] == [1]


class TestSnapshotRepository:
    """Snapshot repository behavior."""

    def test_list_snapshots_filters_by_company(self, snapshot_repo):
        snapshots = snapshot_repo.list_snapshots(company_id=1)
        assert [snapshot.version_number for snapshot in snapshots] == [1, 2]

    def test_list_snapshots_supports_pagination(self, snapshot_repo):
        snapshots = snapshot_repo.list_snapshots(limit=1, offset=1)
        assert len(snapshots) == 1
        assert snapshots[0].version_number == 2

    @pytest.mark.parametrize(
        ("limit", "offset"),
        [(0, 0), (-1, 0), (MAX_PAGE_LIMIT + 1, 0), (1, -1)],
    )
    def test_list_snapshots_rejects_invalid_pagination(
        self, snapshot_repo, limit, offset
    ):
        with pytest.raises(ValueError):
            snapshot_repo.list_snapshots(limit=limit, offset=offset)

    def test_list_snapshots_filters_by_sector_country_currency(self, snapshot_repo):
        snapshots = snapshot_repo.list_snapshots(
            sector="Utilities",
            country="France",
            currency="EUR",
        )
        assert len(snapshots) == 2
        assert all(snapshot.company.rated_entity == "Company A" for snapshot in snapshots)

    def test_list_snapshots_filters_by_date_range(self, snapshot_repo):
        snapshots = snapshot_repo.list_snapshots(
            from_date=date(2024, 1, 2),
            to_date=date(2024, 1, 2),
        )
        assert [snapshot.version_number for snapshot in snapshots] == [2]

    def test_get_snapshot_eager_loads_detail_relationships(self, snapshot_repo):
        snapshot = snapshot_repo.get_snapshot(2)
        assert snapshot is not None
        assert snapshot.company.rated_entity == "Company A"
        assert len(snapshot.industry_segments) == 1
        assert len(snapshot.rating_methodologies) == 1
        assert len(snapshot.scope_metrics) == 1

    def test_get_latest_for_each_company_returns_current_snapshots(self, snapshot_repo):
        snapshots = snapshot_repo.get_latest_for_each_company()
        assert [snapshot.version_number for snapshot in snapshots] == [2, 1]
        assert all(snapshot.is_current for snapshot in snapshots)

    def test_get_as_of_returns_historical_snapshot(self, snapshot_repo):
        snapshot = snapshot_repo.get_as_of(1, date(2024, 1, 1))
        assert snapshot is not None
        assert snapshot.version_number == 1

    def test_count_current(self, snapshot_repo):
        assert snapshot_repo.count_current() == 2


class TestUploadRepository:
    """Upload repository behavior."""

    def test_list_uploads_returns_newest_first(self, upload_repo):
        uploads = upload_repo.list_uploads()
        assert uploads[0].filename == "../secret.xlsm"

    def test_list_uploads_supports_pagination(self, upload_repo):
        uploads = upload_repo.list_uploads(limit=2, offset=1)
        assert [upload.filename for upload in uploads] == ["dup.xlsm", "bad.xlsm"]

    @pytest.mark.parametrize(
        ("limit", "offset"),
        [(0, 0), (-1, 0), (MAX_PAGE_LIMIT + 1, 0), (1, -1)],
    )
    def test_list_uploads_rejects_invalid_pagination(
        self, upload_repo, limit, offset
    ):
        with pytest.raises(ValueError):
            upload_repo.list_uploads(limit=limit, offset=offset)

    def test_get_upload_returns_match(self, upload_repo):
        upload = upload_repo.get_upload(1)
        assert upload is not None
        assert upload.filename == "a_v1.xlsm"

    def test_get_stats_counts_statuses_and_records(self, upload_repo):
        stats = upload_repo.get_stats()
        assert stats.total_uploads == 5
        assert stats.successful == 2
        assert stats.failed == 1
        assert stats.duplicates_skipped == 1
        assert stats.skipped == 1
        assert stats.total_records == 9

    def test_get_source_file_path_returns_existing_path(self, upload_repo):
        path = upload_repo.get_source_file_path(1)
        assert path is not None
        assert path.name == "a_v1.xlsm"

    def test_get_source_file_path_missing_file_returns_none(self, upload_repo):
        assert upload_repo.get_source_file_path(2) is None

    def test_get_source_file_path_blocks_path_traversal(self, upload_repo):
        assert upload_repo.get_source_file_path(5) is None
