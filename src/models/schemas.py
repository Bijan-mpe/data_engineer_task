"""
Pipeline-internal data transfer objects (DTOs).

These models define the data shapes that flow between pipeline stages:
  Extractor  →  ExtractedFile (wraps RawMasterData + file lineage)
  Validator  →  ValidationReport
  Pipeline   →  PipelineRunReport

No ORM or API concerns here — these are plain Pydantic models that carry
extracted and validated data through the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.constants import (
    AccountingPrinciples,
    BusinessYearEnd,
    LiquidityScore,
    PipelineStatus,
    RatingGrade,
)


class IndustrySegment(BaseModel):
    """
    One industry segment within a multi-segment (or single-segment) company.

    Multi-segment companies have multiple columns in the MASTER sheet for
    Industry risk, Industry risk score, and Industry weight rows.  Each
    column maps to one IndustrySegment with a 1-indexed position.
    """

    position: int = Field(ge=1, description="1-indexed column position in the MASTER sheet.")
    industry_name: str
    risk_score: str  # RatingGrade value; kept str so extractor passes raw input unchanged
    weight: float


class ScopeMetric(BaseModel):
    """Single time-series observation from the [Scope Credit Metrics] section.

    Years are stored as integers; the is_estimate flag distinguishes historical
    actuals (e.g. 2023) from forward estimates (e.g. "2026E" in the source).
    Cells labelled "No data" in the source are stored as value=None.
    """

    metric_name: str
    year: int
    is_estimate: bool = False
    value: float | None = None


class RawMasterData(BaseModel):
    """
    All fields extracted from the MASTER sheet of one .xlsm file.

    This is the canonical DTO produced by the extractor and consumed by the
    validator and transformer.  Field names mirror MASTER sheet labels
    converted to snake_case.

    str_strip_whitespace strips leading/trailing whitespace before min_length
    is evaluated, so "   " is rejected the same as "".
    List fields and numeric range constraints are intentionally absent here;
    they are enforced by the validator stage so all violations are collected
    into a single ValidationReport rather than raising on the first failure.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    rated_entity: str = Field(min_length=1)
    corporate_sector: str = Field(min_length=1)
    rating_methodologies: list[str]
    industry_segments: list[IndustrySegment]
    segmentation_criteria: str | None = None
    reporting_currency: str = Field(min_length=1)
    country_of_origin: str = Field(min_length=1)
    accounting_principles: AccountingPrinciples
    business_year_end: BusinessYearEnd
    # Business risk sub-factors
    business_risk_profile: RatingGrade
    blended_industry_risk_profile: RatingGrade
    competitive_positioning: RatingGrade
    market_share: RatingGrade
    diversification: RatingGrade
    operating_profitability: RatingGrade
    sector_specific_factor_1: RatingGrade | None = None
    sector_specific_factor_2: RatingGrade | None = None
    # Financial risk sub-factors
    financial_risk_profile: RatingGrade
    leverage: RatingGrade
    interest_cover: RatingGrade
    cash_flow_cover: RatingGrade
    liquidity: LiquidityScore
    scope_metrics: list[ScopeMetric]


class ExtractedFile(BaseModel):
    """
    File-level wrapper produced by the extractor before validation.

    Carries source lineage (filename, SHA-256 hash, extraction timestamp)
    alongside the extracted MASTER sheet content so every downstream stage —
    validator, transformer, loader — can associate data with its origin file
    and populate the upload_audit record without re-deriving file metadata.
    """

    filename: str = Field(min_length=1)
    file_hash: str = Field(min_length=1)  # SHA-256 hex digest
    extracted_at: datetime
    data: RawMasterData


class FieldError(BaseModel):
    """A single validation failure on a named field."""

    field: str
    raw_value: Any = None
    message: str


class ValidationReport(BaseModel):
    """Outcome of running the validator against one RawMasterData instance."""

    filename: str
    is_valid: bool
    errors: list[FieldError] = Field(default_factory=list)


class PipelineRunReport(BaseModel):
    """
    Summary emitted at the end of processing one source file.

    Carries enough context for structured log emission and for the data quality
    report that the pipeline generates after a full run.
    """

    filename: str
    status: PipelineStatus
    company_name: str | None = None
    validation: ValidationReport | None = None
    error_message: str | None = None
    records_written: int = 0


class LoadPlan(BaseModel):
    """
    Transformed representation ready for the load stage.

    The extractor DTO mirrors the source workbook.  LoadPlan mirrors the
    warehouse write contract: one company identity, one snapshot payload, and
    three child collections.  Keeping this shape separate from DB writes makes
    transformation testable without opening a database transaction.
    """

    filename: str
    file_hash: str
    extracted_at: datetime
    rated_entity: str
    corporate_sector: str
    country_of_origin: str
    reporting_currency: str
    accounting_principles: AccountingPrinciples
    business_year_end: BusinessYearEnd
    segmentation_criteria: str | None = None
    business_risk_profile: RatingGrade
    blended_industry_risk_profile: RatingGrade
    competitive_positioning: RatingGrade
    market_share: RatingGrade
    diversification: RatingGrade
    operating_profitability: RatingGrade
    sector_specific_factor_1: RatingGrade | None = None
    sector_specific_factor_2: RatingGrade | None = None
    financial_risk_profile: RatingGrade
    leverage: RatingGrade
    interest_cover: RatingGrade
    cash_flow_cover: RatingGrade
    liquidity: LiquidityScore
    industry_segments: list[IndustrySegment]
    rating_methodologies: list[str]
    scope_metrics: list[ScopeMetric]


class PipelineBatchReport(BaseModel):
    """
    Run-level report emitted after processing a directory of source files.

    This is the data-quality and execution summary for a full pipeline run:
    per-file reports remain available, while totals are precomputed for logs,
    CI checks, and future sample-output deliverables.
    """

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    files_found: int
    reports: list[PipelineRunReport]
    succeeded: int
    failed: int
    duplicates: int
    records_written: int
    validation_error_count: int
