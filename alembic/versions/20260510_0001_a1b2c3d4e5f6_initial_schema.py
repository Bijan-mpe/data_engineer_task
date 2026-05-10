"""Initial schema: all six tables.

Revision ID: a1b2c3d4e5f6
Revises: —
Create Date: 2026-05-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "upload_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("file_hash", sa.Text, nullable=False),
        sa.Column("status", sa.String(15), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("record_count", sa.Integer, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_upload_audit_file_hash", "upload_audit", ["file_hash"])
    op.create_index(
        "ix_upload_audit_success_file_hash",
        "upload_audit",
        ["file_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'success'"),
    )

    op.create_table(
        "company",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rated_entity", sa.Text, nullable=False),
        sa.Column("corporate_sector", sa.Text, nullable=False),
        sa.Column("country_of_origin", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("rated_entity", "country_of_origin", name="uq_company_identity"),
    )
    op.create_index("ix_company_rated_entity", "company", ["rated_entity"])

    op.create_table(
        "company_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "company_id", sa.Integer, sa.ForeignKey("company.id"), nullable=False
        ),
        sa.Column(
            "upload_id", sa.Integer, sa.ForeignKey("upload_audit.id"), nullable=False
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("reporting_currency", sa.String(10), nullable=False),
        sa.Column("accounting_principles", sa.String(10), nullable=False),
        sa.Column("business_year_end", sa.String(15), nullable=False),
        sa.Column("segmentation_criteria", sa.Text, nullable=True),
        # Business risk sub-factors
        sa.Column("business_risk_profile", sa.String(5), nullable=False),
        sa.Column("blended_industry_risk_profile", sa.String(5), nullable=False),
        sa.Column("competitive_positioning", sa.String(5), nullable=False),
        sa.Column("market_share", sa.String(5), nullable=False),
        sa.Column("diversification", sa.String(5), nullable=False),
        sa.Column("operating_profitability", sa.String(5), nullable=False),
        sa.Column("sector_specific_factor_1", sa.String(5), nullable=True),
        sa.Column("sector_specific_factor_2", sa.String(5), nullable=True),
        # Financial risk sub-factors
        sa.Column("financial_risk_profile", sa.String(5), nullable=False),
        sa.Column("leverage", sa.String(5), nullable=False),
        sa.Column("interest_cover", sa.String(5), nullable=False),
        sa.Column("cash_flow_cover", sa.String(5), nullable=False),
        sa.Column("liquidity", sa.String(15), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "version_number",
            name="uq_company_snapshot_company_version",
        ),
    )
    op.create_index(
        "ix_company_snapshot_is_current", "company_snapshot", ["is_current"]
    )
    op.create_index(
        "ix_company_snapshot_company_current",
        "company_snapshot",
        ["company_id", "is_current"],
    )
    # Partial unique index: enforces at most one current snapshot per company.
    op.create_index(
        "ix_company_snapshot_one_current_per_company",
        "company_snapshot",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "industry_segment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.Integer,
            sa.ForeignKey("company_snapshot.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("industry_name", sa.Text, nullable=False),
        sa.Column("risk_score", sa.String(5), nullable=False),
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "snapshot_id", "position", name="uq_industry_segment_snapshot_position"
        ),
    )

    op.create_table(
        "rating_methodology",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.Integer,
            sa.ForeignKey("company_snapshot.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("methodology_name", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "position",
            name="uq_rating_methodology_snapshot_position",
        ),
    )

    op.create_table(
        "scope_metric",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.Integer,
            sa.ForeignKey("company_snapshot.id"),
            nullable=False,
        ),
        sa.Column("metric_name", sa.Text, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column(
            "is_estimate",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "metric_name",
            "year",
            "is_estimate",
            name="uq_scope_metric_snapshot_metric_year",
        ),
    )


def downgrade() -> None:
    op.drop_table("scope_metric")
    op.drop_table("rating_methodology")
    op.drop_table("industry_segment")
    op.drop_index(
        "ix_company_snapshot_one_current_per_company",
        table_name="company_snapshot",
        postgresql_where=sa.text("is_current = true"),
    )
    op.drop_index(
        "ix_company_snapshot_company_current", table_name="company_snapshot"
    )
    op.drop_index("ix_company_snapshot_is_current", table_name="company_snapshot")
    op.drop_table("company_snapshot")
    op.drop_index("ix_company_rated_entity", table_name="company")
    op.drop_table("company")
    op.drop_index("ix_upload_audit_success_file_hash", table_name="upload_audit")
    op.drop_index("ix_upload_audit_file_hash", table_name="upload_audit")
    op.drop_table("upload_audit")
