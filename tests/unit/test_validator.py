"""
Unit tests for src.pipeline.validator.

All tests use pure in-memory fixtures — no file I/O, no database.

The conftest `make_raw_master_dict` factory produces a minimal valid payload;
individual tests override only the fields under test to keep each case focused.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from src.models.schemas import ExtractedFile, RawMasterData, ValidationReport
from src.pipeline.validator import validate

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_extracted(make_raw_master_dict, **overrides) -> ExtractedFile:
    """Build an ExtractedFile from the base dict, merging *overrides*."""
    return ExtractedFile(
        filename="test_file.xlsm",
        file_hash="a" * 64,
        extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        data=RawMasterData(**make_raw_master_dict(**overrides)),
    )


def _segment(risk_score: str = "A", weight: float = 1.0, position: int = 1) -> dict:
    return {
        "position": position,
        "industry_name": "Consumer Products",
        "risk_score": risk_score,
        "weight": weight,
    }


def _metric(
    metric_name: str = "Scope-adjusted EBITDA interest cover",
    year: int = 2023,
    is_estimate: bool = False,
    value: float | None = 4.862,
) -> dict:
    return {
        "metric_name": metric_name,
        "year": year,
        "is_estimate": is_estimate,
        "value": value,
    }


# ── validate() return type ────────────────────────────────────────────────────

class TestValidateReturnType:
    def test_returns_validation_report(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict)
        result = validate(ef)
        assert isinstance(result, ValidationReport)

    def test_filename_matches_extracted_file(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict)
        assert validate(ef).filename == "test_file.xlsm"

    def test_valid_data_has_no_errors(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict)
        report = validate(ef)
        assert report.is_valid is True
        assert report.errors == []


# ── check 1: industry segment risk_score ─────────────────────────────────────

class TestIndustryRiskScoreValidation:
    def test_valid_risk_score_passes(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="BBB")],
        )
        assert validate(ef).is_valid is True

    def test_invalid_risk_score_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="INVALID")],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert len(report.errors) == 1

    def test_error_references_correct_field(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="NOT_A_GRADE")],
        )
        error = validate(ef).errors[0]
        assert "industry_segments[0].risk_score" in error.field

    def test_error_includes_raw_value(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="JUNK")],
        )
        assert validate(ef).errors[0].raw_value == "JUNK"

    def test_multiple_invalid_segments_all_reported(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BAD1", weight=0.4, position=1),
                _segment(risk_score="BAD2", weight=0.6, position=2),
            ],
        )
        report = validate(ef)
        assert len(report.errors) == 2
        assert any("industry_segments[0]" in e.field for e in report.errors)
        assert any("industry_segments[1]" in e.field for e in report.errors)

    def test_one_bad_one_good_segment(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BBB", weight=0.5, position=1),
                _segment(risk_score="INVALID", weight=0.5, position=2),
            ],
        )
        report = validate(ef)
        assert len(report.errors) == 1
        assert "industry_segments[1]" in report.errors[0].field

    @pytest.mark.parametrize("grade", ["AAA", "A+", "BBB-", "BB", "CCC", "D", "SD"])
    def test_all_valid_rating_grades_pass(self, make_raw_master_dict, grade):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score=grade)],
        )
        assert validate(ef).is_valid is True


# ── check 2: scope metric uniqueness ─────────────────────────────────────────

class TestScopeMetricUniqueness:
    def test_unique_metrics_pass(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[
                _metric(year=2022),
                _metric(year=2023),
            ],
        )
        assert validate(ef).is_valid is True

    def test_same_name_different_years_pass(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[
                _metric(metric_name="Metric A", year=2021),
                _metric(metric_name="Metric A", year=2022),
                _metric(metric_name="Metric A", year=2023),
            ],
        )
        assert validate(ef).is_valid is True

    def test_same_year_different_names_pass(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[
                _metric(metric_name="Metric A", year=2023),
                _metric(metric_name="Metric B", year=2023),
            ],
        )
        assert validate(ef).is_valid is True

    def test_estimate_vs_historical_same_year_pass(self, make_raw_master_dict):
        # (name, 2025, False) and (name, 2025, True) are distinct keys
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[
                _metric(year=2025, is_estimate=False),
                _metric(year=2025, is_estimate=True),
            ],
        )
        assert validate(ef).is_valid is True

    def test_duplicate_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[
                _metric(year=2023),
                _metric(year=2023),  # exact duplicate
            ],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert len(report.errors) == 1

    def test_duplicate_error_field_includes_index(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(year=2023), _metric(year=2023)],
        )
        assert "scope_metrics[1]" in validate(ef).errors[0].field

    def test_three_duplicates_reports_two_errors(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(year=2023), _metric(year=2023), _metric(year=2023)],
        )
        assert len(validate(ef).errors) == 2


# ── check 3: scope metric finiteness ─────────────────────────────────────────

class TestScopeMetricFiniteness:
    def test_finite_value_passes(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=42.0)],
        )
        assert validate(ef).is_valid is True

    def test_none_value_passes(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=None)],
        )
        assert validate(ef).is_valid is True

    def test_nan_value_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=float("nan"))],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert len(report.errors) == 1

    def test_positive_inf_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=math.inf)],
        )
        assert validate(ef).is_valid is False

    def test_negative_inf_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=-math.inf)],
        )
        assert validate(ef).is_valid is False

    def test_non_finite_error_field_references_value(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=float("nan"))],
        )
        assert "scope_metrics[0].value" in validate(ef).errors[0].field

    def test_non_finite_error_includes_raw_value(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(value=float("nan"))],
        )
        assert math.isnan(validate(ef).errors[0].raw_value)


# ── check: non-empty lists ───────────────────────────────────────────────────

class TestNonEmptyListChecks:
    def test_empty_rating_methodologies_error(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, rating_methodologies=[])
        report = validate(ef)
        assert report.is_valid is False
        assert any(e.field == "rating_methodologies" for e in report.errors)

    def test_empty_industry_segments_error(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, industry_segments=[])
        report = validate(ef)
        assert report.is_valid is False
        assert any(e.field == "industry_segments" for e in report.errors)

    def test_empty_scope_metrics_error(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, scope_metrics=[])
        report = validate(ef)
        assert report.is_valid is False
        assert any(e.field == "scope_metrics" for e in report.errors)

    def test_non_empty_lists_pass(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict)
        assert validate(ef).is_valid is True


# ── check: industry segment weight range ─────────────────────────────────────

class TestIndustrySegmentWeightRange:
    def test_zero_weight_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(weight=0.0)],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert any("weight" in e.field for e in report.errors)

    def test_negative_weight_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(weight=-0.1)],
        )
        assert validate(ef).is_valid is False

    def test_weight_above_one_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(weight=1.001)],
        )
        assert validate(ef).is_valid is False

    def test_weight_exactly_one_passes(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(weight=1.0)],
        )
        assert validate(ef).is_valid is True

    def test_weight_error_includes_raw_value(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(weight=0.0)],
        )
        error = next(e for e in validate(ef).errors if "weight" in e.field)
        assert error.raw_value == 0.0


# ── check: industry weight sum ───────────────────────────────────────────────

class TestIndustryWeightSum:
    def test_valid_sum_passes(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BBB", weight=0.15, position=1),
                _segment(risk_score="BB", weight=0.85, position=2),
            ],
        )
        assert validate(ef).is_valid is True

    def test_float_rounding_tolerated(self, make_raw_master_dict):
        # 0.333 + 0.333 + 0.334 = 1.0000000000000002
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BBB", weight=0.333, position=1),
                _segment(risk_score="BB", weight=0.333, position=2),
                _segment(risk_score="B", weight=0.334, position=3),
            ],
        )
        assert validate(ef).is_valid is True

    def test_invalid_sum_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BBB", weight=0.3, position=1),
                _segment(risk_score="BB", weight=0.3, position=2),
            ],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert any("sum" in e.message.lower() or "weights" in e.message.lower()
                   for e in report.errors)

    def test_invalid_sum_error_includes_actual_value(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[
                _segment(risk_score="BBB", weight=0.4, position=1),
                _segment(risk_score="BB", weight=0.4, position=2),
            ],
        )
        report = validate(ef)
        sum_error = next(e for e in report.errors if "segments" in e.field)
        assert "0.800000" in sum_error.message


# ── check: scope metric year range ───────────────────────────────────────────

class TestScopeMetricYearRange:
    def test_valid_year_passes(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, scope_metrics=[_metric(year=2023)])
        assert validate(ef).is_valid is True

    def test_year_below_minimum_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, scope_metrics=[_metric(year=1899)])
        report = validate(ef)
        assert report.is_valid is False
        assert any("year" in e.field for e in report.errors)

    def test_year_above_maximum_produces_error(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, scope_metrics=[_metric(year=2101)])
        assert validate(ef).is_valid is False

    def test_boundary_years_pass(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            scope_metrics=[_metric(year=1900), _metric(year=2100, is_estimate=True)],
        )
        assert validate(ef).is_valid is True

    def test_year_error_includes_raw_value(self, make_raw_master_dict):
        ef = _make_extracted(make_raw_master_dict, scope_metrics=[_metric(year=1800)])
        error = next(e for e in validate(ef).errors if "year" in e.field)
        assert error.raw_value == 1800


# ── multi-error accumulation ──────────────────────────────────────────────────

class TestMultipleErrorAccumulation:
    def test_errors_from_different_checks_all_collected(self, make_raw_master_dict):
        """Bad risk_score + duplicate metric: both errors must appear in one report."""
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="INVALID")],
            scope_metrics=[_metric(year=2023), _metric(year=2023)],
        )
        report = validate(ef)
        assert report.is_valid is False
        assert len(report.errors) == 2

    def test_is_valid_false_when_any_error_present(self, make_raw_master_dict):
        ef = _make_extracted(
            make_raw_master_dict,
            industry_segments=[_segment(risk_score="BAD")],
        )
        assert validate(ef).is_valid is False


# ── real-file smoke tests ─────────────────────────────────────────────────────

@pytest.mark.skipif(
    not __import__("pathlib").Path("data/corporates_A_1.xlsm").exists(),
    reason="data/corporates_A_1.xlsm not present",
)
class TestValidateRealFiles:
    """Smoke-test that all four fixture files pass validation end-to-end."""

    @pytest.fixture(params=["corporates_A_1.xlsm", "corporates_A_2.xlsm",
                            "corporates_B_1.xlsm", "corporates_B_2.xlsm"])
    def extracted(self, request):
        from pathlib import Path  # noqa: PLC0415

        from src.pipeline.extractor import extract_file
        p = Path("data") / request.param
        if not p.exists():
            pytest.skip(f"{request.param} not present")
        return extract_file(p)

    def test_real_file_passes_validation(self, extracted):
        report = validate(extracted)
        assert report.is_valid is True, (
            f"{extracted.filename} failed validation:\n"
            + "\n".join(f"  {e.field}: {e.message}" for e in report.errors)
        )
