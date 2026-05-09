"""
Pydantic response models for the FastAPI layer.

All ORM-backed models use ConfigDict(from_attributes=True) so they can be
constructed directly from SQLAlchemy ORM instances:

    resp = CompanyResponse.model_validate(orm_company)

Models that compose other response models (e.g. SnapshotDetailResponse)
rely on Pydantic's recursive attribute traversal — nested ORM relationships
are serialised automatically as long as every nested model also carries
from_attributes=True.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IndustrySegmentResponse(BaseModel):
    """API representation of one industry segment."""

    model_config = ConfigDict(from_attributes=True)

    position: int
    industry_name: str
    risk_score: str
    weight: float


class RatingMethodologyResponse(BaseModel):
    """API representation of one rating methodology applied to a company."""

    model_config = ConfigDict(from_attributes=True)

    position: int
    methodology_name: str


class ScopeMetricResponse(BaseModel):
    """API representation of one Scope Credit Metric time-series observation."""

    model_config = ConfigDict(from_attributes=True)

    metric_name: str
    year: int
    is_estimate: bool
    value: float | None


class CompanyResponse(BaseModel):
    """Company dimension record — stable identity fields only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rated_entity: str
    corporate_sector: str
    country_of_origin: str


class SnapshotSummaryResponse(BaseModel):
    """Lightweight snapshot row — used in list and comparison endpoints.

    Denormalises key company identity fields so list endpoints need no
    separate JOIN and can filter by sector, country, and currency directly.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    upload_id: int
    version_number: int
    snapshot_date: date
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool
    # denormalised company identity — avoids JOIN on list endpoints
    rated_entity: str
    corporate_sector: str
    country_of_origin: str
    reporting_currency: str
    # key rating signals
    business_risk_profile: str
    financial_risk_profile: str
    liquidity: str


class SnapshotDetailResponse(BaseModel):
    """Full snapshot with all rating sub-factors, segments, methodologies, and metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company: CompanyResponse
    version_number: int
    snapshot_date: date
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool
    reporting_currency: str
    accounting_principles: str
    business_year_end: str
    segmentation_criteria: str | None
    business_risk_profile: str
    blended_industry_risk_profile: str
    competitive_positioning: str
    market_share: str
    diversification: str
    operating_profitability: str
    sector_specific_factor_1: str | None
    sector_specific_factor_2: str | None
    financial_risk_profile: str
    leverage: str
    interest_cover: str
    cash_flow_cover: str
    liquidity: str
    industry_segments: list[IndustrySegmentResponse]
    rating_methodologies: list[RatingMethodologyResponse]
    scope_metrics: list[ScopeMetricResponse]


class UploadAuditResponse(BaseModel):
    """Single upload_audit record — returned by audit list and detail endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_hash: str
    status: str
    created_at: datetime
    processed_at: datetime | None
    record_count: int | None
    error_message: str | None


class UploadStatsResponse(BaseModel):
    """Aggregate counts across all upload_audit records — returned by the stats endpoint."""

    total_uploads: int = 0
    successful: int = 0
    failed: int = 0
    duplicates_skipped: int = 0
    total_records: int = 0


class CompanyHistoryResponse(BaseModel):
    """All snapshots for a single company in chronological order."""

    company: CompanyResponse
    snapshots: list[SnapshotSummaryResponse]


class CompareResponse(BaseModel):
    """Side-by-side snapshot comparison across two or more companies."""

    companies: list[CompanyResponse]
    snapshots: list[SnapshotSummaryResponse]
