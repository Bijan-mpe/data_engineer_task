"""Unit tests for src.models.responses — API response model construction."""

from datetime import date
from types import SimpleNamespace

from src.models.responses import (
    CompanyHistoryResponse,
    CompanyResponse,
    CompareResponse,
    IndustrySegmentResponse,
    RatingMethodologyResponse,
    ScopeMetricResponse,
    SnapshotDetailResponse,
    SnapshotSummaryResponse,
    UploadAuditResponse,
    UploadStatsResponse,
)

# ── from_attributes contract ──────────────────────────────────────────────────

def test_orm_backed_models_have_from_attributes():
    """Every model that is constructed from ORM objects must opt in explicitly."""
    orm_backed = [
        IndustrySegmentResponse,
        RatingMethodologyResponse,
        ScopeMetricResponse,
        CompanyResponse,
        SnapshotSummaryResponse,
        SnapshotDetailResponse,
        UploadAuditResponse,
    ]
    for model in orm_backed:
        assert model.model_config.get("from_attributes") is True, (
            f"{model.__name__} missing from_attributes=True"
        )


# ── individual model round-trips ──────────────────────────────────────────────

def test_company_response_from_orm_object(make_company_ns):
    resp = CompanyResponse.model_validate(make_company_ns())
    assert resp.rated_entity == "Company A"
    assert resp.country_of_origin == "Federal Republic of Germany"


def test_industry_segment_response_from_orm():
    obj = SimpleNamespace(position=1, industry_name="Consumer Products", risk_score="A", weight=1.0)
    resp = IndustrySegmentResponse.model_validate(obj)
    assert resp.weight == 1.0
    assert resp.position == 1


def test_scope_metric_response_none_value():
    """value=None must round-trip cleanly — it represents "No data" cells."""
    obj = SimpleNamespace(
        metric_name="Scope-adjusted loan/value", year=2023, is_estimate=False, value=None
    )
    resp = ScopeMetricResponse.model_validate(obj)
    assert resp.value is None


def test_snapshot_summary_response_from_orm(make_snapshot_ns):
    resp = SnapshotSummaryResponse.model_validate(make_snapshot_ns())
    assert resp.business_risk_profile == "B+"
    assert resp.rated_entity == "Company A"
    assert resp.reporting_currency == "EUR"
    assert isinstance(resp.snapshot_date, date)


def test_snapshot_summary_scd2_fields(make_snapshot_ns, now_utc):
    """SCD2 tracking fields must round-trip; valid_to=None means currently active."""
    resp = SnapshotSummaryResponse.model_validate(make_snapshot_ns())
    assert resp.is_current is True
    assert resp.valid_to is None
    assert resp.valid_from == now_utc


# ── nested SnapshotDetailResponse ────────────────────────────────────────────

def test_snapshot_detail_response_with_nested_objects(make_company_ns, now_utc):
    company = make_company_ns()
    segment = SimpleNamespace(
        position=1, industry_name="Consumer Products", risk_score="A", weight=1.0
    )
    methodology = SimpleNamespace(
        position=1, methodology_name="General Corporate Rating Methodology"
    )
    metric = SimpleNamespace(
        metric_name="Scope-adjusted debt/EBITDA", year=2023, is_estimate=False, value=2.5
    )
    obj = SimpleNamespace(
        id=1,
        company=company,
        version_number=1,
        snapshot_date=date(2024, 1, 1),
        valid_from=now_utc,
        valid_to=None,
        is_current=True,
        reporting_currency="EUR",
        accounting_principles="IFRS",
        business_year_end="December",
        segmentation_criteria=None,
        business_risk_profile="B+",
        blended_industry_risk_profile="A",
        competitive_positioning="B+",
        market_share="BB-",
        diversification="B+",
        operating_profitability="BB-",
        sector_specific_factor_1="B-",
        sector_specific_factor_2=None,
        financial_risk_profile="C",
        leverage="CCC",
        interest_cover="B-",
        cash_flow_cover="CCC",
        liquidity="-2 notches",
        industry_segments=[segment],
        rating_methodologies=[methodology],
        scope_metrics=[metric],
    )
    resp = SnapshotDetailResponse.model_validate(obj)
    assert resp.sector_specific_factor_2 is None
    assert len(resp.industry_segments) == 1
    assert resp.industry_segments[0].risk_score == "A"
    assert resp.scope_metrics[0].value == 2.5


# ── upload audit responses ────────────────────────────────────────────────────

def test_upload_audit_response_from_orm(now_utc):
    obj = SimpleNamespace(
        id=42,
        filename="corporates_A_1.xlsm",
        file_hash="abc123",
        status="success",
        created_at=now_utc,
        processed_at=now_utc,
        record_count=10,
        error_message=None,
    )
    resp = UploadAuditResponse.model_validate(obj)
    assert resp.id == 42
    assert resp.record_count == 10
    assert resp.error_message is None


def test_upload_audit_response_failed_run(now_utc):
    """A failed audit record has processed_at=None and a non-null error_message."""
    obj = SimpleNamespace(
        id=7,
        filename="corporates_A_1.xlsm",
        file_hash="def456",
        status="failed",
        created_at=now_utc,
        processed_at=None,
        record_count=None,
        error_message="missing field: liquidity",
    )
    resp = UploadAuditResponse.model_validate(obj)
    assert resp.processed_at is None
    assert resp.error_message == "missing field: liquidity"


def test_upload_stats_defaults_to_zero():
    stats = UploadStatsResponse()
    assert stats.total_uploads == 0
    assert stats.duplicates_skipped == 0
    assert stats.skipped == 0


# ── aggregate responses ───────────────────────────────────────────────────────

def test_company_history_response(make_company_ns, make_snapshot_ns):
    company = CompanyResponse.model_validate(make_company_ns())
    snapshot = SnapshotSummaryResponse.model_validate(make_snapshot_ns())
    resp = CompanyHistoryResponse(company=company, snapshots=[snapshot])
    assert len(resp.snapshots) == 1
    assert resp.company.rated_entity == "Company A"


def test_compare_response_multiple_companies(make_company_ns):
    c1 = CompanyResponse.model_validate(make_company_ns(rated_entity="Company A"))
    c2 = CompanyResponse.model_validate(
        make_company_ns(rated_entity="Company B", corporate_sector="Automobiles & Parts")
    )
    resp = CompareResponse(companies=[c1, c2], snapshots=[])
    assert len(resp.companies) == 2
    assert {c.rated_entity for c in resp.companies} == {"Company A", "Company B"}
