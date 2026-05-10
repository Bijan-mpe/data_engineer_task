"""Unit tests for FastAPI v1 routes with dependency-overridden SQLite session."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_settings
from src.api.main import create_app
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


@pytest.fixture
def sqlite_engine(tmp_path):
    """File-backed SQLite schema for API tests across TestClient threads."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api_test.db'}")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_company_snapshot_one_current_per_company"))
        conn.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def api_data(sqlite_engine, tmp_path):
    """Seed API test data and return ids plus data directory."""
    session = Session(sqlite_engine)
    ids = _seed_api_data(session, tmp_path)
    session.close()
    return ids, tmp_path


@pytest.fixture
def app(sqlite_engine, api_data):
    """FastAPI app with database and settings dependencies overridden."""
    _ids, data_dir = api_data
    app = create_app()

    async def override_session():
        session = Session(sqlite_engine)
        try:
            yield session
        finally:
            session.close()

    async def override_settings():
        return SimpleNamespace(data_dir=data_dir)

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return app


async def _get(app, path: str, **kwargs) -> httpx.Response:
    """Execute a GET request directly against the ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, **kwargs)


def _seed_api_data(session: Session, data_dir) -> dict[str, int]:
    """Create deterministic rows for API endpoint tests."""
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    (data_dir / "a_v1.xlsm").write_bytes(b"workbook")

    upload_a1 = UploadAudit(
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
    upload_skipped = UploadAudit(
        filename="../outside.xlsm",
        file_hash="d" * 64,
        status=PipelineStatus.SKIPPED,
        processed_at=now,
    )
    session.add_all([upload_a1, upload_a2, upload_failed, upload_skipped])
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

    snapshot_a1 = _make_snapshot(
        company_a.id,
        upload_a1.id,
        version_number=1,
        valid_from=now,
        valid_to=now + timedelta(days=1),
        is_current=False,
        currency="EUR",
    )
    snapshot_a2 = _make_snapshot(
        company_a.id,
        upload_a2.id,
        version_number=2,
        valid_from=now + timedelta(days=1),
        valid_to=None,
        is_current=True,
        currency="EUR",
    )
    snapshot_b1 = _make_snapshot(
        company_b.id,
        upload_a1.id,
        version_number=1,
        valid_from=now,
        valid_to=None,
        is_current=True,
        currency="USD",
    )
    session.add_all([snapshot_a1, snapshot_a2, snapshot_b1])
    session.flush()

    session.add_all(
        [
            IndustrySegment(
                snapshot_id=snapshot_a2.id,
                position=1,
                industry_name="Utilities",
                risk_score="A",
                weight=1.0,
            ),
            RatingMethodology(
                snapshot_id=snapshot_a2.id,
                position=1,
                methodology_name="General Corporate Rating Methodology",
            ),
            ScopeMetric(
                snapshot_id=snapshot_a2.id,
                metric_name="Scope-adjusted debt/EBITDA",
                year=2024,
                is_estimate=False,
                value=2.5,
            ),
        ]
    )
    session.commit()
    return {
        "company_a": company_a.id,
        "company_b": company_b.id,
        "snapshot_a2": snapshot_a2.id,
        "upload_a1": upload_a1.id,
        "upload_skipped": upload_skipped.id,
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
    """Build a complete snapshot for API tests."""
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


@pytest.mark.asyncio
async def test_openapi_available(app):
    response = await _get(app, "/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Scope Ratings Data API"


@pytest.mark.asyncio
async def test_list_companies(app):
    response = await _get(app, "/v1/companies")
    assert response.status_code == 200
    assert [row["rated_entity"] for row in response.json()] == ["Company A", "Company B"]


@pytest.mark.asyncio
async def test_get_company(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/companies/{ids['company_a']}")
    assert response.status_code == 200
    assert response.json()["rated_entity"] == "Company A"


@pytest.mark.asyncio
async def test_get_company_missing_returns_404(app):
    response = await _get(app, "/v1/companies/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_company_versions(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/companies/{ids['company_a']}/versions")
    assert response.status_code == 200
    assert [row["version_number"] for row in response.json()] == [1, 2]


@pytest.mark.asyncio
async def test_get_company_history(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/companies/{ids['company_a']}/history")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["rated_entity"] == "Company A"
    assert [row["version_number"] for row in body["snapshots"]] == [1, 2]


@pytest.mark.asyncio
async def test_compare_companies(app, api_data):
    ids, _data_dir = api_data
    response = await _get(
        app,
        "/v1/companies/compare",
        params=[
            ("company_ids", ids["company_a"]),
            ("company_ids", ids["company_b"]),
            ("as_of_date", "2024-01-02"),
        ],
    )
    assert response.status_code == 200
    assert [row["rated_entity"] for row in response.json()["companies"]] == [
        "Company A",
        "Company B",
    ]


@pytest.mark.asyncio
async def test_compare_companies_missing_snapshot_returns_404(app, api_data):
    ids, _data_dir = api_data
    response = await _get(
        app,
        "/v1/companies/compare",
        params=[
            ("company_ids", ids["company_a"]),
            ("company_ids", 999),
            ("as_of_date", "2024-01-02"),
        ],
    )
    assert response.status_code == 404
    assert response.json()["detail"]["missing_company_ids"] == [999]


@pytest.mark.asyncio
async def test_list_snapshots_with_filters(app):
    response = await _get(
        app,
        "/v1/snapshots",
        params={"sector": "Utilities", "country": "France", "currency": "EUR"},
    )
    assert response.status_code == 200
    assert [row["version_number"] for row in response.json()] == [1, 2]


@pytest.mark.asyncio
async def test_get_latest_snapshots(app):
    response = await _get(app, "/v1/snapshots/latest")
    assert response.status_code == 200
    assert [row["version_number"] for row in response.json()] == [2, 1]


@pytest.mark.asyncio
async def test_get_snapshot_detail(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/snapshots/{ids['snapshot_a2']}")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["rated_entity"] == "Company A"
    assert len(body["industry_segments"]) == 1
    assert len(body["rating_methodologies"]) == 1
    assert len(body["scope_metrics"]) == 1


@pytest.mark.asyncio
async def test_get_snapshot_missing_returns_404(app):
    response = await _get(app, "/v1/snapshots/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_uploads(app):
    response = await _get(app, "/v1/uploads", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_upload_details(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/uploads/{ids['upload_a1']}/details")
    assert response.status_code == 200
    assert response.json()["filename"] == "a_v1.xlsm"


@pytest.mark.asyncio
async def test_get_upload_stats(app):
    response = await _get(app, "/v1/uploads/stats")
    assert response.status_code == 200
    assert response.json()["successful"] == 2
    assert response.json()["failed"] == 1
    assert response.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_get_upload_file(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/uploads/{ids['upload_a1']}/file")
    assert response.status_code == 200
    assert response.content == b"workbook"


@pytest.mark.asyncio
async def test_get_upload_file_blocks_unsafe_path(app, api_data):
    ids, _data_dir = api_data
    response = await _get(app, f"/v1/uploads/{ids['upload_skipped']}/file")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_pagination_returns_422(app):
    response = await _get(app, "/v1/companies", params={"limit": 0})
    assert response.status_code == 422
