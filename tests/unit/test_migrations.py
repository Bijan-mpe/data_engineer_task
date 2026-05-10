"""Unit tests for Alembic migration structure — no DB connection required.

These tests verify that the migration files are well-formed and that the
revision chain is internally consistent.  They do not apply migrations or
inspect the live database (those are integration tests).
"""

import inspect
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path("alembic.ini")
VERSIONS_DIR = Path("alembic/versions")
EXPECTED_TABLES = {
    "upload_audit",
    "company",
    "company_snapshot",
    "industry_segment",
    "rating_methodology",
    "scope_metric",
}


def _script_dir() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def _base_revision():
    """Return the single base Script (down_revision is None)."""
    revisions = list(_script_dir().walk_revisions())
    base = next((r for r in revisions if r.down_revision is None), None)
    assert base is not None, "no base revision found"
    return base


# ── alembic.ini ───────────────────────────────────────────────────────────────

def test_alembic_ini_exists():
    assert ALEMBIC_INI.exists()


def test_alembic_ini_script_location():
    config = Config(str(ALEMBIC_INI))
    assert config.get_main_option("script_location") == "alembic"


def test_alembic_ini_prepends_sys_path():
    """prepend_sys_path = . lets env.py import src.* without extra setup."""
    config = Config(str(ALEMBIC_INI))
    assert config.get_main_option("prepend_sys_path") == "."


# ── revision chain ────────────────────────────────────────────────────────────

def test_versions_directory_is_non_empty():
    migrations = [f for f in VERSIONS_DIR.glob("*.py") if not f.name.startswith("__")]
    assert len(migrations) >= 1


def test_revision_chain_has_exactly_one_head():
    heads = _script_dir().get_heads()
    assert len(heads) == 1, f"expected one head, got: {heads}"


def test_exactly_one_base_revision():
    revisions = list(_script_dir().walk_revisions())
    bases = [r for r in revisions if r.down_revision is None]
    assert len(bases) == 1


def test_revision_ids_are_non_empty_strings():
    for rev in _script_dir().walk_revisions():
        assert isinstance(rev.revision, str) and rev.revision.strip()


# ── initial migration content ─────────────────────────────────────────────────

def test_initial_migration_upgrade_is_callable():
    assert callable(_base_revision().module.upgrade)


def test_initial_migration_downgrade_is_callable():
    assert callable(_base_revision().module.downgrade)


def test_initial_migration_upgrade_references_all_tables():
    source = inspect.getsource(_base_revision().module.upgrade)
    for table in EXPECTED_TABLES:
        assert table in source, f"upgrade() does not reference table '{table}'"


def test_initial_migration_downgrade_references_all_tables():
    source = inspect.getsource(_base_revision().module.downgrade)
    for table in EXPECTED_TABLES:
        assert table in source, f"downgrade() does not reference table '{table}'"


def test_initial_migration_creates_partial_unique_index():
    """The is_current partial unique index must be in the upgrade."""
    source = inspect.getsource(_base_revision().module.upgrade)
    assert "ix_company_snapshot_one_current_per_company" in source
    assert "is_current = true" in source


def test_initial_migration_creates_success_file_hash_unique_index():
    """Successful uploads must be unique by file hash for concurrent idempotency."""
    source = inspect.getsource(_base_revision().module.upgrade)
    assert "ix_upload_audit_success_file_hash" in source
    assert "status = 'success'" in source


def test_initial_migration_drops_partial_unique_index_in_downgrade():
    source = inspect.getsource(_base_revision().module.downgrade)
    assert "ix_company_snapshot_one_current_per_company" in source
    assert "ix_upload_audit_success_file_hash" in source


def test_initial_migration_includes_version_number_column():
    source = inspect.getsource(_base_revision().module.upgrade)
    assert "version_number" in source


def test_initial_migration_includes_company_identity_constraint():
    source = inspect.getsource(_base_revision().module.upgrade)
    assert "uq_company_identity" in source
    assert "rated_entity" in source
    assert "country_of_origin" in source


def test_initial_migration_keeps_company_metadata_out_of_snapshot():
    source = inspect.getsource(_base_revision().module.upgrade)
    snapshot_table_start = source.index('op.create_table(\n        "company_snapshot"')
    industry_table_start = source.index('op.create_table(\n        "industry_segment"')
    snapshot_source = source[snapshot_table_start:industry_table_start]
    assert "corporate_sector" not in snapshot_source
    assert "country_of_origin" not in snapshot_source


def test_initial_migration_includes_audit_timestamps():
    source = inspect.getsource(_base_revision().module.upgrade)
    assert "created_at" in source
    assert "updated_at" in source


# ── offline SQL smoke test ────────────────────────────────────────────────────

def test_alembic_upgrade_sql_smoke():
    """Run alembic upgrade head --sql in offline mode.

    This executes env.py end-to-end without a live DB.  It verifies:
    - alembic.ini is valid
    - env.py imports succeed (catches missing symbols like get_settings)
    - _get_url() returns a usable URL
    - upgrade() emits DDL for every expected table
    """
    import os
    import subprocess

    env = {**os.environ, "POSTGRES_PASSWORD": "test_password"}
    result = subprocess.run(
        ["alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"alembic upgrade --sql exited {result.returncode}:\n{result.stderr}"
    )
    for table in EXPECTED_TABLES:
        assert table in result.stdout, (
            f"SQL output missing CREATE TABLE for '{table}'"
        )
