"""
Validator: runs business-rule checks on extracted data and returns a ValidationReport.

This stage is intentionally separate from Pydantic schema validation.  Pydantic
enforces structural constraints (types, enum membership, non-empty lists) and
raises exceptions on the first violation.  The validator collects *all* violations
across a complete dataset into a structured `ValidationReport`, enabling a
meaningful data-quality report after each pipeline run.

Checks performed
----------------
1. rating_methodologies list is non-empty.
2. industry_segments list is non-empty.
3. scope_metrics list is non-empty.
4. Each industry segment weight is in the range (0, 1].
5. Industry segment weights sum to 1.0 (±0.01 tolerance for float rounding).
6. Industry segment risk_score values are valid RatingGrade members.
   (The schema keeps risk_score as str so the extractor passes raw input through.)
7. Each scope metric year is in [1900, 2100].
8. Scope metric (metric_name, year, is_estimate) tuples are unique within the file.
9. Scope metric float values are mathematically finite (no NaN / Inf).
"""

from __future__ import annotations

import math

from src.core.constants import RatingGrade
from src.models.schemas import (
    ExtractedFile,
    FieldError,
    RawMasterData,
    ValidationReport,
)

_VALID_RATING_GRADES: frozenset[str] = frozenset(g.value for g in RatingGrade)


def validate(extracted: ExtractedFile) -> ValidationReport:
    """Run all business-rule checks against *extracted* and return a ValidationReport.

    Parameters
    ----------
    extracted:
        The ExtractedFile produced by the extractor stage.

    Returns
    -------
    ValidationReport
        ``is_valid=True`` when no errors were found; ``errors`` lists every
        violation so the pipeline can emit a complete data-quality report.
    """
    errors: list[FieldError] = []
    data = extracted.data

    _check_non_empty_lists(data, errors)
    _check_industry_segment_weights(data, errors)
    _check_industry_risk_scores(data, errors)
    _check_scope_metric_years(data, errors)
    _check_scope_metric_uniqueness(data, errors)
    _check_scope_metric_finiteness(data, errors)

    return ValidationReport(
        filename=extracted.filename,
        is_valid=len(errors) == 0,
        errors=errors,
    )


# ── private checks ────────────────────────────────────────────────────────────

_YEAR_MIN = 1900
_YEAR_MAX = 2100


def _check_non_empty_lists(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify the three list fields each contain at least one entry."""
    for field_name, value in (
        ("rating_methodologies", data.rating_methodologies),
        ("industry_segments", data.industry_segments),
        ("scope_metrics", data.scope_metrics),
    ):
        if not value:
            errors.append(
                FieldError(
                    field=field_name,
                    raw_value=value,
                    message=f"'{field_name}' must contain at least one entry",
                )
            )


def _check_industry_segment_weights(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify per-segment weight range and that all weights sum to 1.0.

    Each weight must be in (0, 1].  The sum must be 1.0 ± 0.01 to tolerate
    floating-point rounding (e.g. 0.333 + 0.333 + 0.334 = 1.0000000000000002).
    Both checks are run independently so all violations are reported at once.
    """
    for i, seg in enumerate(data.industry_segments):
        if not (0 < seg.weight <= 1.0):
            errors.append(
                FieldError(
                    field=f"industry_segments[{i}].weight",
                    raw_value=seg.weight,
                    message=(
                        f"weight must be in (0, 1], got {seg.weight}"
                    ),
                )
            )

    if data.industry_segments:
        total = sum(seg.weight for seg in data.industry_segments)
        if not (0.99 <= total <= 1.01):
            errors.append(
                FieldError(
                    field="industry_segments",
                    raw_value=total,
                    message=(
                        f"industry_segments weights must sum to 1.0 "
                        f"(got {total:.6f})"
                    ),
                )
            )


def _check_scope_metric_years(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify each scope metric year is in [{_YEAR_MIN}, {_YEAR_MAX}]."""
    for i, m in enumerate(data.scope_metrics):
        if not (_YEAR_MIN <= m.year <= _YEAR_MAX):
            errors.append(
                FieldError(
                    field=f"scope_metrics[{i}].year",
                    raw_value=m.year,
                    message=(
                        f"year {m.year} is outside the allowed range "
                        f"[{_YEAR_MIN}, {_YEAR_MAX}]"
                    ),
                )
            )


def _check_industry_risk_scores(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify each industry segment's risk_score is a valid RatingGrade value.

    The IndustrySegment schema stores risk_score as a plain str so the extractor
    can pass raw cell text through without Pydantic raising on extraction.  The
    validator catches any value that doesn't match the controlled vocabulary.
    """
    for i, seg in enumerate(data.industry_segments):
        if seg.risk_score not in _VALID_RATING_GRADES:
            errors.append(
                FieldError(
                    field=f"industry_segments[{i}].risk_score",
                    raw_value=seg.risk_score,
                    message=(
                        f"'{seg.risk_score}' is not a valid RatingGrade value. "
                        f"Expected one of: {sorted(_VALID_RATING_GRADES)}"
                    ),
                )
            )


def _check_scope_metric_uniqueness(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify no two scope metrics share the same (metric_name, year, is_estimate) key.

    Duplicates would cause a database unique-constraint violation at load time.
    Collecting them here turns a hard failure into a reportable data-quality issue.
    """
    seen: set[tuple[str, int, bool]] = set()
    for i, m in enumerate(data.scope_metrics):
        key = (m.metric_name, m.year, m.is_estimate)
        if key in seen:
            errors.append(
                FieldError(
                    field=f"scope_metrics[{i}]",
                    raw_value=key,
                    message=(
                        f"Duplicate scope metric: metric_name='{m.metric_name}' "
                        f"year={m.year} is_estimate={m.is_estimate}"
                    ),
                )
            )
        else:
            seen.add(key)


def _check_scope_metric_finiteness(data: RawMasterData, errors: list[FieldError]) -> None:
    """Verify that non-None scope metric values are finite (not NaN or Inf).

    openpyxl can return float('nan') or float('inf') for certain Excel error
    cells.  Such values would corrupt downstream aggregations silently.
    """
    for i, m in enumerate(data.scope_metrics):
        if m.value is not None and not math.isfinite(m.value):
            errors.append(
                FieldError(
                    field=f"scope_metrics[{i}].value",
                    raw_value=m.value,
                    message=(
                        f"Non-finite value for metric '{m.metric_name}' "
                        f"year={m.year}: {m.value}"
                    ),
                )
            )
