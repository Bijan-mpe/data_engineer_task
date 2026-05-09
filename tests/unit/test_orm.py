"""Unit tests for src.models.orm — table definitions and metadata inspection.

These tests verify schema structure without a live database connection.
All assertions are against SQLAlchemy's metadata objects, which are built
at import time from the ORM class definitions.
"""


import pytest
from sqlalchemy import Enum, Integer, UniqueConstraint
from sqlalchemy.orm import RelationshipProperty

from src.core.constants import PipelineStatus
from src.core.db import Base
from src.models.orm import (
    Company,
    CompanySnapshot,
    IndustrySegment,
    RatingMethodology,
    ScopeMetric,
    UploadAudit,
)

# ── table registration ────────────────────────────────────────────────────────

def test_all_six_tables_registered():
    assert set(Base.metadata.tables.keys()) == {
        "upload_audit",
        "company",
        "company_snapshot",
        "industry_segment",
        "rating_methodology",
        "scope_metric",
    }


# ── primary key types ─────────────────────────────────────────────────────────

def test_upload_audit_pk_is_autoincrement_integer():
    col = UploadAudit.__table__.c["id"]
    assert col.primary_key
    assert isinstance(col.type, Integer)
    assert col.autoincrement


def test_company_pk_is_autoincrement_integer():
    col = Company.__table__.c["id"]
    assert col.primary_key
    assert isinstance(col.type, Integer)
    assert col.autoincrement


def test_company_snapshot_pk_is_autoincrement_integer():
    col = CompanySnapshot.__table__.c["id"]
    assert col.primary_key
    assert isinstance(col.type, Integer)
    assert col.autoincrement


@pytest.mark.parametrize("model", [IndustrySegment, RatingMethodology, ScopeMetric])
def test_child_table_pk_is_autoincrement_integer(model):
    col = model.__table__.c["id"]
    assert col.primary_key
    assert isinstance(col.type, Integer)
    assert col.autoincrement


# ── nullable constraints ──────────────────────────────────────────────────────

def test_company_snapshot_valid_to_nullable():
    assert CompanySnapshot.__table__.c["valid_to"].nullable


def test_company_snapshot_segmentation_criteria_nullable():
    assert CompanySnapshot.__table__.c["segmentation_criteria"].nullable


def test_company_snapshot_sector_factors_nullable():
    assert CompanySnapshot.__table__.c["sector_specific_factor_1"].nullable
    assert CompanySnapshot.__table__.c["sector_specific_factor_2"].nullable


def test_scope_metric_value_nullable():
    assert ScopeMetric.__table__.c["value"].nullable


def test_upload_audit_error_message_nullable():
    assert UploadAudit.__table__.c["error_message"].nullable


def test_upload_audit_processed_at_nullable():
    assert UploadAudit.__table__.c["processed_at"].nullable


# ── version_number ────────────────────────────────────────────────────────────

def test_company_snapshot_version_number_not_nullable():
    col = CompanySnapshot.__table__.c["version_number"]
    assert isinstance(col.type, Integer)
    assert not col.nullable


def test_company_snapshot_company_version_unique_constraint():
    """(company_id, version_number) must have a unique constraint."""
    constraint_col_sets = {
        frozenset(col.name for col in c.columns)
        for c in CompanySnapshot.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert frozenset({"company_id", "version_number"}) in constraint_col_sets


# ── audit timestamps ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "model",
    [UploadAudit, Company, CompanySnapshot, IndustrySegment, RatingMethodology, ScopeMetric],
)
def test_all_tables_have_created_at_and_updated_at(model):
    assert "created_at" in model.__table__.c, f"{model.__tablename__} missing created_at"
    assert "updated_at" in model.__table__.c, f"{model.__tablename__} missing updated_at"


def test_created_at_not_nullable():
    assert not CompanySnapshot.__table__.c["created_at"].nullable


def test_updated_at_not_nullable():
    assert not CompanySnapshot.__table__.c["updated_at"].nullable


# ── foreign key wiring ────────────────────────────────────────────────────────

def test_company_snapshot_upload_id_is_integer_fk_to_upload_audit():
    col = CompanySnapshot.__table__.c["upload_id"]
    assert isinstance(col.type, Integer)
    targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "upload_audit.id" in targets


def test_company_snapshot_company_id_fk_to_company():
    col = CompanySnapshot.__table__.c["company_id"]
    assert isinstance(col.type, Integer)
    targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "company.id" in targets


def test_industry_segment_snapshot_id_fk_to_company_snapshot():
    col = IndustrySegment.__table__.c["snapshot_id"]
    assert isinstance(col.type, Integer)
    targets = {fk.target_fullname for fk in col.foreign_keys}
    assert "company_snapshot.id" in targets


# ── enum value storage (values, not member names) ─────────────────────────────

def test_rating_grade_columns_store_values_not_names():
    """Enum columns must store 'BBB-' not 'BBB_MINUS'."""
    col = CompanySnapshot.__table__.c["business_risk_profile"]
    assert isinstance(col.type, Enum)
    stored = set(col.type.enums)
    assert "BBB-" in stored
    assert "BBB_MINUS" not in stored


def test_pipeline_status_column_stores_values():
    col = UploadAudit.__table__.c["status"]
    stored = set(col.type.enums)
    assert "duplicate" in stored
    assert "DUPLICATE" not in stored


# ── indexes ───────────────────────────────────────────────────────────────────

def test_upload_audit_file_hash_indexed():
    assert UploadAudit.__table__.c["file_hash"].index


def test_company_snapshot_is_current_indexed():
    assert CompanySnapshot.__table__.c["is_current"].index


def test_company_snapshot_composite_index_on_company_and_current():
    index_col_sets = {
        frozenset(col.name for col in idx.columns)
        for idx in CompanySnapshot.__table__.indexes
    }
    assert frozenset({"company_id", "is_current"}) in index_col_sets


def test_company_rated_entity_indexed():
    assert Company.__table__.c["rated_entity"].index


# ── relationships ─────────────────────────────────────────────────────────────

def test_company_has_snapshots_relationship():
    rel: RelationshipProperty = Company.snapshots.property
    assert rel.mapper.class_ is CompanySnapshot


def test_company_snapshot_has_industry_segments_relationship():
    rel: RelationshipProperty = CompanySnapshot.industry_segments.property
    assert rel.mapper.class_ is IndustrySegment


# ── cascade delete-orphan on child tables ─────────────────────────────────────

@pytest.mark.parametrize("rel_name", ["industry_segments", "rating_methodologies", "scope_metrics"])
def test_child_relationships_cascade_delete_orphan(rel_name: str):
    rel: RelationshipProperty = getattr(CompanySnapshot, rel_name).property
    assert "delete-orphan" in rel.cascade


# ── repr sanity ───────────────────────────────────────────────────────────────

def test_upload_audit_repr():
    obj = UploadAudit(id=1, filename="corporates_A_1.xlsm", status=PipelineStatus.SUCCESS)
    assert "corporates_A_1.xlsm" in repr(obj)


def test_company_repr():
    obj = Company(rated_entity="Company A")
    assert "Company A" in repr(obj)


def test_company_snapshot_repr_includes_version():
    obj = CompanySnapshot(id=1, company_id=1, version_number=2, is_current=False)
    assert "version=2" in repr(obj)


# ── CompanySnapshot identity properties ──────────────────────────────────────

def test_company_snapshot_has_identity_properties():
    """rated_entity/corporate_sector/country_of_origin must be Python properties."""
    assert isinstance(CompanySnapshot.rated_entity, property)
    assert isinstance(CompanySnapshot.corporate_sector, property)
    assert isinstance(CompanySnapshot.country_of_origin, property)


def test_company_snapshot_identity_properties_delegate_to_company():
    """Call fget directly with a namespace to avoid SQLAlchemy instrumentation setup."""
    from types import SimpleNamespace
    company = SimpleNamespace(
        rated_entity="Acme Corp",
        corporate_sector="Technology",
        country_of_origin="Germany",
    )
    snapshot = SimpleNamespace(company=company)
    assert CompanySnapshot.rated_entity.fget(snapshot) == "Acme Corp"
    assert CompanySnapshot.corporate_sector.fget(snapshot) == "Technology"
    assert CompanySnapshot.country_of_origin.fget(snapshot) == "Germany"


# ── child table unique constraints ────────────────────────────────────────────

def test_industry_segment_unique_constraint_snapshot_position():
    col_sets = {
        frozenset(col.name for col in c.columns)
        for c in IndustrySegment.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert frozenset({"snapshot_id", "position"}) in col_sets


def test_rating_methodology_unique_constraint_snapshot_position():
    col_sets = {
        frozenset(col.name for col in c.columns)
        for c in RatingMethodology.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert frozenset({"snapshot_id", "position"}) in col_sets


def test_scope_metric_unique_constraint_snapshot_metric_year():
    col_sets = {
        frozenset(col.name for col in c.columns)
        for c in ScopeMetric.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert frozenset({"snapshot_id", "metric_name", "year", "is_estimate"}) in col_sets
