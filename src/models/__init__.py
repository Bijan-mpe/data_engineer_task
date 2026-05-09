"""
Data model package — three complementary layers.

Modules
-------
schemas    Pipeline-internal DTOs (ExtractedFile, RawMasterData, ValidationReport, etc.)
responses  FastAPI response models (CompanyResponse, SnapshotDetailResponse, etc.)
orm        SQLAlchemy ORM table definitions (Step 4)

See docs/data_model.md for the full ERD.
"""

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
from src.models.schemas import (
    ExtractedFile,
    FieldError,
    IndustrySegment,
    PipelineRunReport,
    RawMasterData,
    ScopeMetric,
    ValidationReport,
)

__all__ = [
    # schemas
    "IndustrySegment",
    "ScopeMetric",
    "RawMasterData",
    "ExtractedFile",
    "FieldError",
    "ValidationReport",
    "PipelineRunReport",
    # responses
    "IndustrySegmentResponse",
    "RatingMethodologyResponse",
    "ScopeMetricResponse",
    "CompanyResponse",
    "SnapshotSummaryResponse",
    "SnapshotDetailResponse",
    "UploadAuditResponse",
    "UploadStatsResponse",
    "CompanyHistoryResponse",
    "CompareResponse",
]
