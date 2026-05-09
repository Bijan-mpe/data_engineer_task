"""Unit tests for src.models.schemas — pipeline DTO validation constraints."""

import pytest
from pydantic import ValidationError

from src.core.constants import PipelineStatus
from src.models.schemas import (
    ExtractedFile,
    FieldError,
    IndustrySegment,
    PipelineRunReport,
    RawMasterData,
    ScopeMetric,
    ValidationReport,
)

# ── IndustrySegment ───────────────────────────────────────────────────────────

def test_industry_segment_valid_single():
    seg = IndustrySegment(position=1, industry_name="Consumer Products", risk_score="A", weight=1.0)
    assert seg.position == 1
    assert seg.weight == 1.0


def test_industry_segment_weight_zero_rejected():
    with pytest.raises(ValidationError):
        IndustrySegment(position=1, industry_name="X", risk_score="A", weight=0.0)


def test_industry_segment_weight_above_one_rejected():
    with pytest.raises(ValidationError):
        IndustrySegment(position=1, industry_name="X", risk_score="A", weight=1.001)


def test_industry_segment_position_zero_rejected():
    with pytest.raises(ValidationError):
        IndustrySegment(position=0, industry_name="X", risk_score="A", weight=0.5)


# ── ScopeMetric ───────────────────────────────────────────────────────────────

def test_scope_metric_estimate_flag():
    m = ScopeMetric(
        metric_name="Scope-adjusted debt/EBITDA", year=2026, is_estimate=True, value=3.5
    )
    assert m.is_estimate is True
    assert m.year == 2026


def test_scope_metric_none_value_allowed():
    """'No data' cells in the source map to value=None — must not be rejected."""
    m = ScopeMetric(metric_name="Scope-adjusted loan/value", year=2023)
    assert m.value is None
    assert m.is_estimate is False


def test_scope_metric_year_bounds_rejected():
    with pytest.raises(ValidationError):
        ScopeMetric(metric_name="X", year=1899)
    with pytest.raises(ValidationError):
        ScopeMetric(metric_name="X", year=2101)


# ── RawMasterData — string field constraints ──────────────────────────────────

@pytest.mark.parametrize(
    "field", ["rated_entity", "corporate_sector", "reporting_currency", "country_of_origin"]
)
def test_raw_master_data_empty_string_rejected(field: str, make_raw_master_dict):
    with pytest.raises(ValidationError):
        RawMasterData(**make_raw_master_dict(**{field: ""}))


@pytest.mark.parametrize(
    "field", ["rated_entity", "corporate_sector", "reporting_currency", "country_of_origin"]
)
def test_raw_master_data_whitespace_only_rejected(field: str, make_raw_master_dict):
    """str_strip_whitespace strips before min_length check — "   " must be rejected."""
    with pytest.raises(ValidationError):
        RawMasterData(**make_raw_master_dict(**{field: "   "}))


# ── RawMasterData — weight sum validator ──────────────────────────────────────

def test_raw_master_data_weight_sum_valid_multi_segment(make_raw_master_dict):
    data = RawMasterData(
        **make_raw_master_dict(
            industry_segments=[
                {"position": 1, "industry_name": "Seg A", "risk_score": "BBB", "weight": 0.15},
                {"position": 2, "industry_name": "Seg B", "risk_score": "BB", "weight": 0.85},
            ]
        )
    )
    assert len(data.industry_segments) == 2


def test_raw_master_data_weight_sum_float_rounding_tolerated(make_raw_master_dict):
    """0.333 + 0.333 + 0.334 = 1.0000000000000002 — must not be rejected."""
    data = RawMasterData(
        **make_raw_master_dict(
            industry_segments=[
                {"position": 1, "industry_name": "Seg A", "risk_score": "BBB", "weight": 0.333},
                {"position": 2, "industry_name": "Seg B", "risk_score": "BB", "weight": 0.333},
                {"position": 3, "industry_name": "Seg C", "risk_score": "B", "weight": 0.334},
            ]
        )
    )
    assert len(data.industry_segments) == 3


def test_raw_master_data_weight_sum_invalid_rejected(make_raw_master_dict):
    with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
        RawMasterData(
            **make_raw_master_dict(
                industry_segments=[
                    {"position": 1, "industry_name": "Seg A", "risk_score": "BBB", "weight": 0.3},
                    {"position": 2, "industry_name": "Seg B", "risk_score": "BB", "weight": 0.3},
                ]
            )
        )


def test_raw_master_data_weight_sum_error_includes_actual_value(make_raw_master_dict):
    """Error message must include the actual sum for debugging."""
    with pytest.raises(ValidationError) as exc_info:
        RawMasterData(
            **make_raw_master_dict(
                industry_segments=[
                    {"position": 1, "industry_name": "Seg A", "risk_score": "BBB", "weight": 0.4},
                    {"position": 2, "industry_name": "Seg B", "risk_score": "BB", "weight": 0.4},
                ]
            )
        )
    assert "0.800000" in str(exc_info.value)


# ── RawMasterData ─────────────────────────────────────────────────────────────

def test_raw_master_data_company_a_valid(raw_master_data):
    assert raw_master_data.rated_entity == "Company A"
    assert len(raw_master_data.industry_segments) == 1
    assert raw_master_data.industry_segments[0].risk_score == "A"


def test_raw_master_data_company_b_multi_segment(make_raw_master_dict):
    data = RawMasterData(
        **make_raw_master_dict(
            industry_segments=[
                {
                    "position": 1,
                    "industry_name": "Automotive Suppliers",
                    "risk_score": "BBB",
                    "weight": 0.15,
                },
                {
                    "position": 2,
                    "industry_name": "Automotive and Commercial Vehicle Manufacturers",
                    "risk_score": "BB",
                    "weight": 0.85,
                },
            ]
        )
    )
    assert len(data.industry_segments) == 2
    assert data.industry_segments[1].weight == 0.85


def test_raw_master_data_optional_fields_absent(raw_master_data):
    assert raw_master_data.segmentation_criteria is None
    assert raw_master_data.sector_specific_factor_1 is None
    assert raw_master_data.sector_specific_factor_2 is None


def test_raw_master_data_empty_methodologies_rejected(make_raw_master_dict):
    with pytest.raises(ValidationError):
        RawMasterData(**make_raw_master_dict(rating_methodologies=[]))


def test_raw_master_data_empty_segments_rejected(make_raw_master_dict):
    with pytest.raises(ValidationError):
        RawMasterData(**make_raw_master_dict(industry_segments=[]))


def test_raw_master_data_empty_metrics_rejected(make_raw_master_dict):
    with pytest.raises(ValidationError):
        RawMasterData(**make_raw_master_dict(scope_metrics=[]))


# ── FieldError / ValidationReport ────────────────────────────────────────────

def test_validation_report_valid_file():
    report = ValidationReport(filename="corporates_A_1.xlsm", is_valid=True)
    assert report.is_valid
    assert report.errors == []


def test_validation_report_stores_field_errors():
    err = FieldError(field="liquidity", raw_value="bad_value", message="not a valid LiquidityScore")
    report = ValidationReport(filename="corporates_A_1.xlsm", is_valid=False, errors=[err])
    assert not report.is_valid
    assert report.errors[0].raw_value == "bad_value"


def test_field_error_raw_value_accepts_any_type():
    """raw_value must accept numbers, strings, None, and complex objects."""
    assert FieldError(field="x", raw_value=42, message="m").raw_value == 42
    assert FieldError(field="x", raw_value=None, message="m").raw_value is None
    assert FieldError(field="x", raw_value={"k": "v"}, message="m").raw_value == {"k": "v"}


# ── PipelineRunReport ─────────────────────────────────────────────────────────

def test_pipeline_run_report_success():
    report = PipelineRunReport(
        filename="corporates_A_1.xlsm",
        status=PipelineStatus.SUCCESS,
        company_name="Company A",
        records_written=10,
    )
    assert report.status == PipelineStatus.SUCCESS
    assert report.records_written == 10
    assert report.error_message is None


def test_pipeline_run_report_failed_defaults():
    """A failed run has records_written=0 and no company_name by default."""
    report = PipelineRunReport(
        filename="corporates_A_1.xlsm",
        status=PipelineStatus.FAILED,
        error_message="missing field: liquidity",
    )
    assert report.records_written == 0
    assert report.company_name is None


# ── ExtractedFile ─────────────────────────────────────────────────────────────

def test_extracted_file_wraps_raw_master_data(raw_master_data, now_utc):
    """ExtractedFile must carry file lineage alongside the extracted content."""
    ef = ExtractedFile(
        filename="corporates_A_1.xlsm",
        file_hash="a" * 64,
        extracted_at=now_utc,
        data=raw_master_data,
    )
    assert ef.filename == "corporates_A_1.xlsm"
    assert ef.data.rated_entity == "Company A"


def test_extracted_file_empty_filename_rejected(raw_master_data, now_utc):
    with pytest.raises(ValidationError):
        ExtractedFile(filename="", file_hash="a" * 64, extracted_at=now_utc, data=raw_master_data)
