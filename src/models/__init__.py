"""
Data model package — three complementary layers.

Modules
-------
schemas    Pipeline-internal DTOs (ExtractedFile, RawMasterData, ValidationReport, etc.)
responses  FastAPI response models (CompanyResponse, SnapshotDetailResponse, etc.)
orm        SQLAlchemy ORM table definitions

See docs/data_model.md for the full ERD.

Import convention
-----------------
ORM classes are imported from src.models.orm directly (not from this package)
because two schema classes share names with ORM classes: IndustrySegment and
ScopeMetric.  Exposing both sets under the same package-level name would be
ambiguous.  This package re-exports ORM classes that have no naming conflict.
"""

from src.models.orm import (
    Company,
    CompanySnapshot,
    RatingMethodology,
    UploadAudit,
)
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
    # orm (non-conflicting names only — import IndustrySegment/ScopeMetric from src.models.orm)
    "UploadAudit",
    "Company",
    "CompanySnapshot",
    "RatingMethodology",
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
