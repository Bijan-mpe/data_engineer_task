"""
SQLAlchemy ORM table definitions.

Reflects the star schema described in docs/architecture/data_model.md.  All models
inherit from Base (src.core.db) so Alembic and the session factory see a
single metadata registry.

Enum columns use native_enum=False (VARCHAR storage) rather than PostgreSQL
native ENUM types.  This avoids ALTER TYPE migrations whenever an enum value
is added and keeps the Alembic history clean at the cost of no DB-side type
enforcement (which Pydantic handles at the application boundary).

All primary keys are SERIAL integers for readability in logs and queries.
version_number on CompanySnapshot is application-managed: the pipeline
computes MAX(version_number) WHERE company_id=? + 1 inside a transaction.
The DB enforces correctness via the unique constraint on (company_id, version_number).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column, relationship

from src.core.constants import (
    AccountingPrinciples,
    BusinessYearEnd,
    LiquidityScore,
    PipelineStatus,
    RatingGrade,
)
from src.core.db import Base

# ── column helpers ────────────────────────────────────────────────────────────
# Avoid repeating the Enum definition across the 10+ RatingGrade columns.
#
# values_callable tells SQLAlchemy to store the enum .value ("BBB-") rather
# than the member name ("BBB_MINUS").  Without it, native_enum=False falls
# back to name-based storage, which breaks round-trips for str-valued enums.

def _by_value(enum_cls) -> list[str]:
    """Return enum string values; used as values_callable for all Enum columns."""
    return [e.value for e in enum_cls]


def _rating_grade(**kw) -> MappedColumn:
    """VARCHAR(5) column that stores and reads RatingGrade enum values."""
    return mapped_column(
        Enum(RatingGrade, native_enum=False, values_callable=_by_value, length=5), **kw
    )


def _liquidity(**kw) -> MappedColumn:
    """VARCHAR(15) column that stores and reads LiquidityScore enum values."""
    return mapped_column(
        Enum(LiquidityScore, native_enum=False, values_callable=_by_value, length=15), **kw
    )


# ── ORM models ────────────────────────────────────────────────────────────────

class UploadAudit(Base):
    """One row per pipeline run against a source .xlsm file.

    file_hash (SHA-256) is the idempotency key — a duplicate hash is skipped.
    filename is not unique because the same name may carry different content.
    """

    __tablename__ = "upload_audit"
    __table_args__ = (
        Index(
            "ix_upload_audit_success_file_hash",
            "file_hash",
            unique=True,
            postgresql_where=text("status = 'success'"),
            sqlite_where=text("status = 'success'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # index=True for fast duplicate-detection lookup; NOT unique because the same
    # hash legitimately appears multiple times — once as success, then as duplicate
    # on subsequent re-submissions (each run gets its own audit row).
    file_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, native_enum=False, values_callable=_by_value, length=15),
        nullable=False,
        default=PipelineStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list[CompanySnapshot]] = relationship(
        "CompanySnapshot", back_populates="upload"
    )

    def __repr__(self) -> str:
        return f"<UploadAudit id={self.id} filename={self.filename!r} status={self.status}>"


class Company(Base):
    """Stable company identity dimension.

    Rated entity plus country of origin is the natural key.  The sector column
    is retained here with the company identity so snapshot rows do not
    duplicate company metadata.
    """

    __tablename__ = "company"
    __table_args__ = (
        UniqueConstraint("rated_entity", "country_of_origin", name="uq_company_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rated_entity: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    corporate_sector: Mapped[str] = mapped_column(Text, nullable=False)
    country_of_origin: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list[CompanySnapshot]] = relationship(
        "CompanySnapshot",
        back_populates="company",
        order_by="CompanySnapshot.valid_from",
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} rated_entity={self.rated_entity!r}>"


class CompanySnapshot(Base):
    """SCD Type 2 snapshot — one row per source file × company.

    When a newer file version arrives, the previous row's valid_to is closed
    and is_current is set to False before the new row is inserted.
    is_current is a convenience shortcut for WHERE valid_to IS NULL.

    version_number is application-managed: the pipeline sets it to
    MAX(version_number) + 1 for the same company_id inside the load
    transaction.  The unique constraint enforces no two snapshots share the
    same (company_id, version_number) pair.
    """

    __tablename__ = "company_snapshot"
    __table_args__ = (
        Index("ix_company_snapshot_company_current", "company_id", "is_current"),
        # Partial unique index: at most one current snapshot per company in PostgreSQL.
        # WHY: a plain unique constraint on (company_id) would block SCD2 history rows.
        Index(
            "ix_company_snapshot_one_current_per_company",
            "company_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        UniqueConstraint(
            "company_id", "version_number", name="uq_company_snapshot_company_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company.id"), nullable=False
    )
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("upload_audit.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )

    reporting_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    accounting_principles: Mapped[AccountingPrinciples] = mapped_column(
        Enum(AccountingPrinciples, native_enum=False, values_callable=_by_value, length=10),
        nullable=False,
    )
    business_year_end: Mapped[BusinessYearEnd] = mapped_column(
        Enum(BusinessYearEnd, native_enum=False, values_callable=_by_value, length=15),
        nullable=False,
    )
    segmentation_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Business risk sub-factors
    business_risk_profile: Mapped[RatingGrade] = _rating_grade(nullable=False)
    blended_industry_risk_profile: Mapped[RatingGrade] = _rating_grade(nullable=False)
    competitive_positioning: Mapped[RatingGrade] = _rating_grade(nullable=False)
    market_share: Mapped[RatingGrade] = _rating_grade(nullable=False)
    diversification: Mapped[RatingGrade] = _rating_grade(nullable=False)
    operating_profitability: Mapped[RatingGrade] = _rating_grade(nullable=False)
    sector_specific_factor_1: Mapped[Optional[RatingGrade]] = _rating_grade(nullable=True)
    sector_specific_factor_2: Mapped[Optional[RatingGrade]] = _rating_grade(nullable=True)

    # Financial risk sub-factors
    financial_risk_profile: Mapped[RatingGrade] = _rating_grade(nullable=False)
    leverage: Mapped[RatingGrade] = _rating_grade(nullable=False)
    interest_cover: Mapped[RatingGrade] = _rating_grade(nullable=False)
    cash_flow_cover: Mapped[RatingGrade] = _rating_grade(nullable=False)
    liquidity: Mapped[LiquidityScore] = _liquidity(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Denormalised identity properties — read company fields directly on the snapshot.
    # SnapshotSummaryResponse uses from_attributes=True and expects these as flat attrs.
    # The repository layer must eagerly load the `company` relationship before serialising.
    @property
    def rated_entity(self) -> str:
        return self.company.rated_entity

    @property
    def corporate_sector(self) -> str:
        return self.company.corporate_sector

    @property
    def country_of_origin(self) -> str:
        return self.company.country_of_origin

    # Relationships
    company: Mapped[Company] = relationship("Company", back_populates="snapshots")
    upload: Mapped[UploadAudit] = relationship("UploadAudit", back_populates="snapshots")
    industry_segments: Mapped[list[IndustrySegment]] = relationship(
        "IndustrySegment",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="IndustrySegment.position",
    )
    rating_methodologies: Mapped[list[RatingMethodology]] = relationship(
        "RatingMethodology",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="RatingMethodology.position",
    )
    scope_metrics: Mapped[list[ScopeMetric]] = relationship(
        "ScopeMetric",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<CompanySnapshot id={self.id} company_id={self.company_id}"
            f" version={self.version_number} is_current={self.is_current}>"
        )


class IndustrySegment(Base):
    """One row per segment column in the MASTER sheet for a given snapshot.

    position mirrors the 1-indexed column order so segments can be retrieved
    in the original sheet order.
    """

    __tablename__ = "industry_segment"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "position", name="uq_industry_segment_snapshot_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_snapshot.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    industry_name: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[str] = mapped_column(String(5), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshot: Mapped[CompanySnapshot] = relationship(
        "CompanySnapshot", back_populates="industry_segments"
    )

    def __repr__(self) -> str:
        return (
            f"<IndustrySegment snapshot_id={self.snapshot_id}"
            f" position={self.position} industry={self.industry_name!r}>"
        )


class RatingMethodology(Base):
    """One row per methodology applied to a company snapshot.

    position preserves the left-to-right column order from the MASTER sheet.
    """

    __tablename__ = "rating_methodology"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "position", name="uq_rating_methodology_snapshot_position"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_snapshot.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshot: Mapped[CompanySnapshot] = relationship(
        "CompanySnapshot", back_populates="rating_methodologies"
    )

    def __repr__(self) -> str:
        return (
            f"<RatingMethodology snapshot_id={self.snapshot_id}"
            f" position={self.position} name={self.methodology_name!r}>"
        )


class ScopeMetric(Base):
    """One time-series observation from the [Scope Credit Metrics] section.

    value is NULL when the source cell contains "No data".
    is_estimate distinguishes historical actuals from forward estimates
    (e.g. "2026E" in the source becomes year=2026, is_estimate=True).
    """

    __tablename__ = "scope_metric"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "metric_name", "year", "is_estimate",
            name="uq_scope_metric_snapshot_metric_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_snapshot.id"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_estimate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    snapshot: Mapped[CompanySnapshot] = relationship(
        "CompanySnapshot", back_populates="scope_metrics"
    )

    def __repr__(self) -> str:
        return (
            f"<ScopeMetric snapshot_id={self.snapshot_id}"
            f" metric={self.metric_name!r} year={self.year}>"
        )
