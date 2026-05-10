"""
Unit tests for src.pipeline.pipeline.Pipeline.

All tests use SQLite in-memory so no PostgreSQL connection is required.
The PostgreSQL partial unique index is dropped in the SQLite fixture because
SQLite cannot preserve the PostgreSQL-only predicate.

Fixtures build real ExtractedFile objects from the make_raw_master_dict
conftest factory rather than mocking, so the tests exercise the full
transform/load path against a real schema.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.core.constants import PipelineStatus
from src.core.db import Base
from src.models.orm import Company, RatingMethodology, UploadAudit
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.models.orm import IndustrySegment as OrmSegment
from src.models.orm import ScopeMetric as OrmMetric
from src.models.schemas import (
    ExtractedFile,
    FieldError,
    LoadPlan,
    PipelineBatchReport,
    RawMasterData,
    ValidationReport,
)
from src.pipeline.pipeline import Pipeline

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sqlite_engine():
    """SQLite in-memory engine with all ORM tables created.

    The production model has a PostgreSQL-only partial unique index that allows
    historical snapshots while enforcing one current snapshot per company.
    SQLite ignores the PostgreSQL predicate and creates a plain unique index on
    company_id, so logic tests drop it and verify the invariant directly.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_company_snapshot_one_current_per_company"))
        conn.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine):
    """Isolated session for each test.

    Unlike the outer-transaction rollback pattern, the pipeline code calls
    session.commit() directly (for audit records), which would bypass an outer
    SAVEPOINT and leave rows committed.  Instead, all tables are truncated after
    each test to guarantee isolation.
    """
    session = Session(sqlite_engine)
    yield session
    session.close()
    with sqlite_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def pipeline(db_session):
    return Pipeline(db_session)


def _make_extracted(make_raw_master_dict, **overrides) -> ExtractedFile:
    return ExtractedFile(
        filename="corporates_A_1.xlsm",
        file_hash="a" * 64,
        extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        data=RawMasterData(**make_raw_master_dict(**overrides)),
    )


def _valid_report(filename: str = "corporates_A_1.xlsm") -> ValidationReport:
    """Return a successful ValidationReport for patched validator calls."""
    return ValidationReport(filename=filename, is_valid=True)


# ── transform ─────────────────────────────────────────────────────────────────

class TestTransform:
    def test_transform_returns_load_plan(self, pipeline, make_raw_master_dict):
        extracted = _make_extracted(make_raw_master_dict)
        plan = pipeline.transform(extracted)
        assert isinstance(plan, LoadPlan)

    def test_transform_preserves_identity_and_history_fields(
        self, pipeline, make_raw_master_dict
    ):
        extracted = _make_extracted(
            make_raw_master_dict,
            rated_entity="Shared Name",
            corporate_sector="Utilities",
            country_of_origin="France",
        )
        plan = pipeline.transform(extracted)
        assert plan.rated_entity == "Shared Name"
        assert plan.corporate_sector == "Utilities"
        assert plan.country_of_origin == "France"


# ── process_file: success path ────────────────────────────────────────────────

class TestProcessFileSuccess:
    def test_returns_success_report(self, pipeline, make_raw_master_dict, tmp_path):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            report = pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert report.status == PipelineStatus.SUCCESS

    def test_report_includes_company_name(self, pipeline, make_raw_master_dict, tmp_path):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            report = pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert report.company_name == "Company A"

    def test_report_records_written_positive(self, pipeline, make_raw_master_dict, tmp_path):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            report = pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert report.records_written > 0

    def test_company_row_created(self, pipeline, db_session, make_raw_master_dict, tmp_path):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        companies = db_session.execute(select(Company)).scalars().all()
        assert len(companies) == 1
        assert companies[0].rated_entity == "Company A"

    def test_snapshot_created_is_current(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        snapshots = db_session.execute(select(OrmSnapshot)).scalars().all()
        assert len(snapshots) == 1
        assert snapshots[0].is_current is True
        assert snapshots[0].version_number == 1

    def test_snapshot_valid_to_is_none(self, pipeline, db_session, make_raw_master_dict, tmp_path):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        snap = db_session.execute(select(OrmSnapshot)).scalar_one()
        assert snap.valid_to is None

    def test_upload_audit_committed_success(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        audit = db_session.execute(select(UploadAudit)).scalar_one()
        assert audit.status == PipelineStatus.SUCCESS.value
        assert audit.file_hash == "a" * 64

    def test_industry_segments_loaded(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        segments = db_session.execute(select(OrmSegment)).scalars().all()
        assert len(segments) == 1
        assert segments[0].industry_name == "Consumer Products: Non-Discretionary"

    def test_rating_methodologies_loaded(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        methodologies = db_session.execute(select(RatingMethodology)).scalars().all()
        assert len(methodologies) == 1
        assert methodologies[0].methodology_name == "General Corporate Rating Methodology"

    def test_scope_metrics_loaded(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        metrics = db_session.execute(select(OrmMetric)).scalars().all()
        assert len(metrics) == 1
        assert metrics[0].metric_name == "Scope-adjusted EBITDA interest cover"


# ── process_file: SCD2 second version ────────────────────────────────────────

class TestProcessFileSCD2:
    def _load_version(
        self, pipeline, make_raw_master_dict, tmp_path, file_hash, filename, **overrides
    ):
        extracted = ExtractedFile(
            filename=filename,
            file_hash=file_hash,
            extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            data=RawMasterData(**make_raw_master_dict(**overrides)),
        )
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report(filename)
            return pipeline.process_file(tmp_path / filename)

    def test_second_version_increments_version_number(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "a" * 64, "v1.xlsm")
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "b" * 64, "v2.xlsm")
        snapshots = db_session.execute(
            select(OrmSnapshot).order_by(OrmSnapshot.version_number)
        ).scalars().all()
        assert [s.version_number for s in snapshots] == [1, 2]

    def test_only_one_current_snapshot_after_two_versions(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "a" * 64, "v1.xlsm")
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "b" * 64, "v2.xlsm")
        current = db_session.execute(
            select(OrmSnapshot).where(OrmSnapshot.is_current.is_(True))
        ).scalars().all()
        assert len(current) == 1
        assert current[0].version_number == 2

    def test_first_snapshot_closed_after_second_version(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "a" * 64, "v1.xlsm")
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "b" * 64, "v2.xlsm")
        v1 = db_session.execute(
            select(OrmSnapshot).where(OrmSnapshot.version_number == 1)
        ).scalar_one()
        assert v1.is_current is False
        assert v1.valid_to is not None

    def test_single_company_row_despite_two_versions(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "a" * 64, "v1.xlsm")
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "b" * 64, "v2.xlsm")
        companies = db_session.execute(select(Company)).scalars().all()
        assert len(companies) == 1

    def test_same_name_different_country_creates_distinct_companies(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(
            pipeline,
            make_raw_master_dict,
            tmp_path,
            "a" * 64,
            "us.xlsm",
            rated_entity="Shared Name",
            country_of_origin="USA",
        )
        self._load_version(
            pipeline,
            make_raw_master_dict,
            tmp_path,
            "b" * 64,
            "de.xlsm",
            rated_entity="Shared Name",
            country_of_origin="Germany",
        )
        companies = db_session.execute(
            select(Company).order_by(Company.country_of_origin)
        ).scalars().all()
        assert len(companies) == 2
        assert [c.country_of_origin for c in companies] == ["Germany", "USA"]

    def test_company_sector_is_updated_without_snapshot_duplication(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(
            pipeline,
            make_raw_master_dict,
            tmp_path,
            "a" * 64,
            "v1.xlsm",
            corporate_sector="Utilities",
            country_of_origin="France",
        )
        self._load_version(
            pipeline,
            make_raw_master_dict,
            tmp_path,
            "b" * 64,
            "v2.xlsm",
            corporate_sector="Infrastructure",
            country_of_origin="France",
        )
        snapshots = db_session.execute(
            select(OrmSnapshot).order_by(OrmSnapshot.version_number)
        ).scalars().all()
        company = db_session.execute(select(Company)).scalar_one()
        assert company.corporate_sector == "Infrastructure"
        assert company.country_of_origin == "France"
        assert "corporate_sector" not in OrmSnapshot.__table__.c
        assert "country_of_origin" not in OrmSnapshot.__table__.c
        assert len(snapshots) == 2

    def test_next_version_uses_max_existing_version(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        self._load_version(pipeline, make_raw_master_dict, tmp_path, "a" * 64, "v1.xlsm")
        current = db_session.execute(select(OrmSnapshot)).scalar_one()
        current.version_number = 5
        db_session.commit()

        self._load_version(pipeline, make_raw_master_dict, tmp_path, "b" * 64, "v2.xlsm")
        versions = db_session.execute(
            select(OrmSnapshot.version_number).order_by(OrmSnapshot.version_number)
        ).scalars().all()
        assert versions == [5, 6]


# ── process_file: duplicate detection ────────────────────────────────────────

class TestProcessFileDuplicate:
    def test_duplicate_hash_returns_duplicate_status(
        self, pipeline, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")

        # second run with same hash
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted):
            report = pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert report.status == PipelineStatus.DUPLICATE

    def test_duplicate_does_not_create_second_snapshot(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.return_value = _valid_report()
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")

        with patch("src.pipeline.pipeline.extract_file", return_value=extracted):
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")

        snapshots = db_session.execute(select(OrmSnapshot)).scalars().all()
        assert len(snapshots) == 1


# ── process_file: validation failure ─────────────────────────────────────────

class TestProcessFileValidationFailure:
    def test_validation_failure_returns_failed_status(
        self, pipeline, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        bad_report = ValidationReport(
            filename="corporates_A_1.xlsm",
            is_valid=False,
            errors=[
                FieldError(
                    field="industry_segments[0].risk_score",
                    raw_value="JUNK",
                    message="invalid grade",
                )
            ],
        )
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate", return_value=bad_report):
            report = pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert report.status == PipelineStatus.FAILED

    def test_validation_failure_does_not_load_data(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        bad_report = ValidationReport(
            filename="corporates_A_1.xlsm",
            is_valid=False,
            errors=[FieldError(field="f", raw_value=None, message="bad")],
        )
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate", return_value=bad_report):
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        assert db_session.execute(select(OrmSnapshot)).scalars().all() == []

    def test_audit_record_written_on_validation_failure(
        self, pipeline, db_session, make_raw_master_dict, tmp_path
    ):
        extracted = _make_extracted(make_raw_master_dict)
        bad_report = ValidationReport(
            filename="corporates_A_1.xlsm",
            is_valid=False,
            errors=[FieldError(field="f", raw_value=None, message="bad")],
        )
        with patch("src.pipeline.pipeline.extract_file", return_value=extracted), \
             patch("src.pipeline.pipeline.validate", return_value=bad_report):
            pipeline.process_file(tmp_path / "corporates_A_1.xlsm")
        audit = db_session.execute(select(UploadAudit)).scalar_one()
        assert audit.status == PipelineStatus.FAILED.value


# ── process_file: extraction error ───────────────────────────────────────────

class TestProcessFileExtractionError:
    def test_extraction_error_returns_failed_status(self, pipeline, tmp_path):
        from src.pipeline.extractor import ExtractionError
        with patch(
            "src.pipeline.pipeline.extract_file",
            side_effect=ExtractionError("bad file"),
        ):
            report = pipeline.process_file(tmp_path / "bad.xlsm")
        assert report.status == PipelineStatus.FAILED

    def test_extraction_error_message_propagated(self, pipeline, tmp_path):
        from src.pipeline.extractor import ExtractionError
        with patch(
            "src.pipeline.pipeline.extract_file",
            side_effect=ExtractionError("missing MASTER sheet"),
        ):
            report = pipeline.process_file(tmp_path / "bad.xlsm")
        assert "missing MASTER sheet" in report.error_message

    def test_audit_record_written_on_extraction_error(
        self, pipeline, db_session, tmp_path
    ):
        from src.pipeline.extractor import ExtractionError
        with patch(
            "src.pipeline.pipeline.extract_file",
            side_effect=ExtractionError("bad file"),
        ):
            pipeline.process_file(tmp_path / "bad.xlsm")
        audit = db_session.execute(select(UploadAudit)).scalar_one()
        assert audit.status == PipelineStatus.FAILED.value


# ── process_directory ─────────────────────────────────────────────────────────

class TestProcessDirectory:
    def test_empty_directory_returns_empty_list(self, pipeline, tmp_path):
        reports = pipeline.process_directory(tmp_path)
        assert reports == []

    def test_returns_one_report_per_file(self, pipeline, make_raw_master_dict, tmp_path):
        # Create two stub .xlsm files
        (tmp_path / "a.xlsm").write_bytes(b"stub")
        (tmp_path / "b.xlsm").write_bytes(b"stub")

        def fake_extract(path):
            return ExtractedFile(
                filename=path.name,
                file_hash=path.name,  # unique per file
                extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                data=RawMasterData(**make_raw_master_dict(rated_entity=path.stem)),
            )

        with patch("src.pipeline.pipeline.extract_file", side_effect=fake_extract), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.side_effect = lambda extracted: _valid_report(extracted.filename)
            reports = pipeline.process_directory(tmp_path)

        assert len(reports) == 2

    def test_files_processed_in_lexicographic_order(
        self, pipeline, make_raw_master_dict, tmp_path
    ):
        (tmp_path / "b.xlsm").write_bytes(b"stub")
        (tmp_path / "a.xlsm").write_bytes(b"stub")
        processed: list[str] = []

        def fake_extract(path):
            processed.append(path.name)
            return ExtractedFile(
                filename=path.name,
                file_hash=path.name,
                extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                data=RawMasterData(**make_raw_master_dict(rated_entity=path.stem)),
            )

        with patch("src.pipeline.pipeline.extract_file", side_effect=fake_extract), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.side_effect = lambda extracted: _valid_report(extracted.filename)
            pipeline.process_directory(tmp_path)

        assert processed == ["a.xlsm", "b.xlsm"]

    def test_process_directory_report_returns_run_level_metrics(
        self, pipeline, make_raw_master_dict, tmp_path
    ):
        (tmp_path / "a.xlsm").write_bytes(b"stub")
        (tmp_path / "b.xlsm").write_bytes(b"stub")

        def fake_extract(path):
            return ExtractedFile(
                filename=path.name,
                file_hash=path.name,
                extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                data=RawMasterData(**make_raw_master_dict(rated_entity=path.stem)),
            )

        with patch("src.pipeline.pipeline.extract_file", side_effect=fake_extract), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.side_effect = lambda extracted: _valid_report(extracted.filename)
            report = pipeline.process_directory_report(tmp_path)

        assert isinstance(report, PipelineBatchReport)
        assert report.files_found == 2
        assert report.succeeded == 2
        assert report.failed == 0
        assert report.records_written > 0

    def test_process_directory_report_writes_quality_report(
        self, pipeline, make_raw_master_dict, tmp_path
    ):
        data_dir = tmp_path / "data"
        report_dir = tmp_path / "reports"
        data_dir.mkdir()
        (data_dir / "a.xlsm").write_bytes(b"stub")

        def fake_extract(path):
            return ExtractedFile(
                filename=path.name,
                file_hash=path.name,
                extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                data=RawMasterData(**make_raw_master_dict(rated_entity=path.stem)),
            )

        with patch("src.pipeline.pipeline.extract_file", side_effect=fake_extract), \
             patch("src.pipeline.pipeline.validate") as mock_validate:
            mock_validate.side_effect = lambda extracted: _valid_report(extracted.filename)
            pipeline.process_directory_report(data_dir, report_dir=report_dir)

        files = list(report_dir.glob("data_quality_report_*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["files_found"] == 1
        assert payload["succeeded"] == 1
        assert payload["validation_error_count"] == 0


# ── retry handling ────────────────────────────────────────────────────────────

class TestLoadRetry:
    def test_load_with_retry_retries_transient_operational_error(
        self, pipeline, make_raw_master_dict
    ):
        plan = pipeline.transform(_make_extracted(make_raw_master_dict))
        transient = OperationalError("insert", {}, Exception("temporary unavailable"))
        with patch.object(pipeline, "load", side_effect=[transient, 7]) as mock_load, \
             patch("src.pipeline.pipeline.time.sleep") as mock_sleep:
            records_written = pipeline._load_with_retry(
                plan,
                datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        assert records_written == 7
        assert mock_load.call_count == 2
        mock_sleep.assert_called_once()

    def test_load_with_retry_stops_after_max_attempts(self, pipeline, make_raw_master_dict):
        plan = pipeline.transform(_make_extracted(make_raw_master_dict))
        transient = OperationalError("insert", {}, Exception("temporary unavailable"))
        with patch.object(pipeline, "load", side_effect=transient) as mock_load, \
             patch("src.pipeline.pipeline.time.sleep"):
            with pytest.raises(OperationalError):
                pipeline._load_with_retry(plan, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert mock_load.call_count == 3

    def test_load_with_retry_retries_company_identity_race(
        self, pipeline, make_raw_master_dict
    ):
        plan = pipeline.transform(_make_extracted(make_raw_master_dict))
        race = IntegrityError(
            "insert",
            {},
            Exception('duplicate key value violates unique constraint "uq_company_identity"'),
        )
        with patch.object(pipeline, "load", side_effect=[race, 8]) as mock_load, \
             patch("src.pipeline.pipeline.time.sleep") as mock_sleep:
            records_written = pipeline._load_with_retry(
                plan,
                datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        assert records_written == 8
        assert mock_load.call_count == 2
        mock_sleep.assert_called_once()

    def test_load_with_retry_does_not_retry_other_integrity_errors(
        self, pipeline, make_raw_master_dict
    ):
        plan = pipeline.transform(_make_extracted(make_raw_master_dict))
        not_company_race = IntegrityError(
            "insert",
            {},
            Exception('duplicate key value violates unique constraint "other_constraint"'),
        )
        with patch.object(pipeline, "load", side_effect=not_company_race) as mock_load, \
             patch("src.pipeline.pipeline.time.sleep") as mock_sleep:
            with pytest.raises(IntegrityError):
                pipeline._load_with_retry(plan, datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert mock_load.call_count == 1
        mock_sleep.assert_not_called()
