"""Unit tests for src.models.schemas — structural well-formedness constraints.

Only Pydantic-level invariants are tested here: correct types, enum membership,
required vs optional fields, and non-empty string constraints.  Business-rule
checks (weight range, weight sum, year range, non-empty lists) live in
test_validator.py where they are exercised via the validator stage.
"""

import pytest
from pydantic import ValidationError

from src.core.constants import PipelineStatus
from src.models.schemas import (
    ExtractedFile,
    FieldError,
    IndustrySegment,
    LoadPlan,
    PipelineBatchReport,
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


# ── LoadPlan / PipelineBatchReport ────────────────────────────────────────────

def test_load_plan_accepts_transformed_payload(raw_master_data, now_utc):
    plan = LoadPlan(
        filename="corporates_A_1.xlsm",
        file_hash="a" * 64,
        extracted_at=now_utc,
        **raw_master_data.model_dump(),
    )
    assert plan.rated_entity == "Company A"
    assert plan.country_of_origin == raw_master_data.country_of_origin


def test_pipeline_batch_report_stores_totals(now_utc):
    report = PipelineBatchReport(
        started_at=now_utc,
        finished_at=now_utc,
        duration_seconds=0.0,
        files_found=1,
        reports=[
            PipelineRunReport(
                filename="corporates_A_1.xlsm",
                status=PipelineStatus.SUCCESS,
                records_written=4,
            )
        ],
        succeeded=1,
        failed=0,
        duplicates=0,
        records_written=4,
        validation_error_count=0,
    )
    assert report.files_found == 1
    assert report.records_written == 4


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
