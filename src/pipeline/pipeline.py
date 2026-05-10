"""
Pipeline: orchestrates extract → validate → transform → load for each source file.

One Pipeline instance handles one run against a SQLAlchemy Session.  The caller
(typically main() below) is responsible for opening and closing the session.

Transaction strategy
--------------------
Each file is processed in its own commit boundary:
  • Success path: audit record + all data objects committed together.
  • Failure path: main transaction is rolled back; a minimal audit record
    is then committed in a separate, fresh transaction so the failure is
    always traceable even when the data write fails.

SCD Type 2
----------
Company identity (rated_entity, country) lives in the Company table.
Each file version produces a new CompanySnapshot row.  Before inserting the
new snapshot the existing current row (is_current=True) is closed by setting
valid_to=now and is_current=False.  version_number is application-managed:
MAX(version_number) + 1 within the same company_id.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.core.constants import DATA_FILE_EXTENSION, PipelineStatus
from src.core.logging import get_logger
from src.models.orm import (
    Company,
    RatingMethodology,
    UploadAudit,
)
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.models.orm import IndustrySegment as OrmSegment
from src.models.orm import ScopeMetric as OrmMetric
from src.models.schemas import (
    ExtractedFile,
    LoadPlan,
    PipelineBatchReport,
    PipelineRunReport,
    ValidationReport,
)
from src.pipeline.extractor import ExtractionError, extract_file
from src.pipeline.validator import validate

logger = get_logger(__name__)

_MAX_LOAD_ATTEMPTS = 3
_COMPANY_IDENTITY_CONSTRAINT = "uq_company_identity"


class Pipeline:
    """Orchestrates extract → validate → transform → load for .xlsm files.

    Parameters
    ----------
    session:
        An open SQLAlchemy Session.  The caller owns its lifecycle; Pipeline
        never closes the session.

    Usage
    -----
        with session_scope() as session:
            pipeline = Pipeline(session)
            reports = pipeline.process_directory(Path("data"))
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── public API ────────────────────────────────────────────────────────────

    def extract(self, path: Path) -> ExtractedFile:
        """Extract source data and lineage from one workbook."""
        return extract_file(path)

    def validate_extracted(self, extracted: ExtractedFile) -> ValidationReport:
        """Validate extracted data before transformation and loading."""
        return validate(extracted)

    def transform(self, extracted: ExtractedFile) -> LoadPlan:
        """Map extracted source data into the load-stage contract."""
        data = extracted.data
        return LoadPlan(
            filename=extracted.filename,
            file_hash=extracted.file_hash,
            extracted_at=extracted.extracted_at,
            rated_entity=data.rated_entity,
            corporate_sector=data.corporate_sector,
            country_of_origin=data.country_of_origin,
            reporting_currency=data.reporting_currency,
            accounting_principles=data.accounting_principles,
            business_year_end=data.business_year_end,
            segmentation_criteria=data.segmentation_criteria,
            business_risk_profile=data.business_risk_profile,
            blended_industry_risk_profile=data.blended_industry_risk_profile,
            competitive_positioning=data.competitive_positioning,
            market_share=data.market_share,
            diversification=data.diversification,
            operating_profitability=data.operating_profitability,
            sector_specific_factor_1=data.sector_specific_factor_1,
            sector_specific_factor_2=data.sector_specific_factor_2,
            financial_risk_profile=data.financial_risk_profile,
            leverage=data.leverage,
            interest_cover=data.interest_cover,
            cash_flow_cover=data.cash_flow_cover,
            liquidity=data.liquidity,
            industry_segments=data.industry_segments,
            rating_methodologies=data.rating_methodologies,
            scope_metrics=data.scope_metrics,
        )

    def load(self, plan: LoadPlan, now: datetime) -> int:
        """Persist one transformed load plan and return written data rows."""
        audit = UploadAudit(
            filename=plan.filename,
            file_hash=plan.file_hash,
            status=PipelineStatus.RUNNING,
        )
        self._session.add(audit)
        self._session.flush()

        records_written = self._load_data(plan, audit.id, now)

        audit.status = PipelineStatus.SUCCESS
        audit.processed_at = now
        audit.record_count = records_written
        self._session.commit()
        return records_written

    def process_file(self, path: Path) -> PipelineRunReport:
        """Process one .xlsm file end-to-end and return a run report.

        Steps:
        1. Extract — parse MASTER sheet and compute file hash.
        2. Duplicate check — skip if hash already loaded successfully.
        3. Validate — run all business-rule checks.
        4. Load — write Company, CompanySnapshot, and child records.

        On any failure the main transaction is rolled back and a minimal
        audit record is committed in a separate transaction.
        """
        now = datetime.now(tz=timezone.utc)
        logger.info("Processing: %s", path.name)

        # ── 1. extract ────────────────────────────────────────────────────────
        try:
            extracted = self.extract(path)
        except ExtractionError as exc:
            logger.error("Extraction failed for %s: %s", path.name, exc)
            self._write_audit(path.name, "", PipelineStatus.FAILED, str(exc), now)
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.FAILED,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected extraction failure for %s: %s", path.name, exc)
            self._write_audit(path.name, "", PipelineStatus.FAILED, str(exc), now)
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.FAILED,
                error_message=str(exc),
            )

        # ── 2. duplicate check ────────────────────────────────────────────────
        if self._is_duplicate(extracted.file_hash):
            logger.info("Duplicate: %s (hash already loaded)", path.name)
            self._write_audit(path.name, extracted.file_hash, PipelineStatus.DUPLICATE, None, now)
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.DUPLICATE,
                company_name=extracted.data.rated_entity,
            )

        # ── 3. validate ───────────────────────────────────────────────────────
        validation = self.validate_extracted(extracted)
        if not validation.is_valid:
            error_msg = "; ".join(
                f"{e.field}: {e.message}" for e in validation.errors
            )
            logger.warning("Validation failed for %s: %s", path.name, error_msg)
            self._write_audit(path.name, extracted.file_hash, PipelineStatus.FAILED, error_msg, now)
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.FAILED,
                company_name=extracted.data.rated_entity,
                validation=validation,
                error_message=error_msg,
            )

        # ── 4. load ───────────────────────────────────────────────────────────
        load_plan = self.transform(extracted)
        try:
            records_written = self._load_with_retry(load_plan, now)
        except IntegrityError as exc:
            self._session.rollback()
            if self._is_duplicate(extracted.file_hash):
                logger.info("Duplicate detected by database constraint: %s", path.name)
                self._write_audit(
                    path.name,
                    extracted.file_hash,
                    PipelineStatus.DUPLICATE,
                    None,
                    now,
                )
                return PipelineRunReport(
                    filename=path.name,
                    status=PipelineStatus.DUPLICATE,
                    company_name=extracted.data.rated_entity,
                    validation=validation,
                )
            logger.exception("Load constraint failed for %s: %s", path.name, exc)
            self._write_audit(
                path.name, extracted.file_hash, PipelineStatus.FAILED, str(exc), now
            )
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.FAILED,
                company_name=extracted.data.rated_entity,
                validation=validation,
                error_message=str(exc),
            )
        except Exception as exc:
            self._session.rollback()
            logger.exception("Load failed for %s: %s", path.name, exc)
            self._write_audit(
                path.name, extracted.file_hash, PipelineStatus.FAILED, str(exc), now
            )
            return PipelineRunReport(
                filename=path.name,
                status=PipelineStatus.FAILED,
                company_name=extracted.data.rated_entity,
                validation=validation,
                error_message=str(exc),
            )

        logger.info(
            "Loaded %s → %s (%d records)",
            path.name,
            extracted.data.rated_entity,
            records_written,
        )
        return PipelineRunReport(
            filename=path.name,
            status=PipelineStatus.SUCCESS,
            company_name=extracted.data.rated_entity,
            validation=validation,
            records_written=records_written,
        )

    def process_directory(self, data_dir: Path) -> list[PipelineRunReport]:
        """Process all .xlsm files in *data_dir* in lexicographic order.

        Parameters
        ----------
        data_dir:
            Directory containing source .xlsm files.

        Returns
        -------
        list[PipelineRunReport]
            One report per file found; empty list when no files are present.
        """
        return self.process_directory_report(data_dir).reports

    def process_directory_report(self, data_dir: Path) -> PipelineBatchReport:
        """Process a directory and return run-level metrics and quality counts."""
        started_at = datetime.now(tz=timezone.utc)
        files = sorted(data_dir.glob(f"*{DATA_FILE_EXTENSION}"))
        if not files:
            logger.warning("No %s files found in %s", DATA_FILE_EXTENSION, data_dir)
            finished_at = datetime.now(tz=timezone.utc)
            return PipelineBatchReport(
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                files_found=0,
                reports=[],
                succeeded=0,
                failed=0,
                duplicates=0,
                records_written=0,
                validation_error_count=0,
            )

        reports = [self.process_file(f) for f in files]
        finished_at = datetime.now(tz=timezone.utc)
        return PipelineBatchReport(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=(finished_at - started_at).total_seconds(),
            files_found=len(files),
            reports=reports,
            succeeded=sum(1 for r in reports if r.status == PipelineStatus.SUCCESS),
            failed=sum(1 for r in reports if r.status == PipelineStatus.FAILED),
            duplicates=sum(1 for r in reports if r.status == PipelineStatus.DUPLICATE),
            records_written=sum(r.records_written for r in reports),
            validation_error_count=sum(
                len(r.validation.errors) for r in reports if r.validation is not None
            ),
        )

    # ── private helpers ───────────────────────────────────────────────────────

    def _is_duplicate(self, file_hash: str) -> bool:
        """Return True if *file_hash* was already committed with status SUCCESS."""
        result = self._session.execute(
            select(UploadAudit).where(
                UploadAudit.file_hash == file_hash,
                UploadAudit.status == PipelineStatus.SUCCESS,
            )
        ).first()
        return result is not None

    def _write_audit(
        self,
        filename: str,
        file_hash: str,
        status: PipelineStatus,
        error_message: str | None,
        processed_at: datetime,
    ) -> None:
        """Commit a standalone audit record in its own transaction.

        Called after the main transaction has been rolled back (or was never
        started) so that every pipeline run always leaves a traceable record.
        Swallows exceptions to ensure the caller's control flow is not disrupted.
        """
        try:
            audit = UploadAudit(
                filename=filename,
                file_hash=file_hash,
                status=status,
                error_message=error_message,
                processed_at=processed_at if status != PipelineStatus.PENDING else None,
            )
            self._session.add(audit)
            self._session.commit()
        except Exception:
            self._session.rollback()
            logger.exception("Failed to write audit record for %s", filename)

    def _load_with_retry(self, plan: LoadPlan, now: datetime) -> int:
        """Run load with bounded retries for transient database failures.

        A concurrent first load for the same company can race on the
        ``uq_company_identity`` constraint.  Retrying the full load lets the
        loser roll back its failed insert, re-read the company created by the
        winner, and continue with the normal SCD2 path.
        """
        for attempt in range(1, _MAX_LOAD_ATTEMPTS + 1):
            try:
                return self.load(plan, now)
            except IntegrityError as exc:
                self._session.rollback()
                if not self._is_company_identity_race(exc) or attempt == _MAX_LOAD_ATTEMPTS:
                    raise
                delay = 0.1 * (2 ** (attempt - 1))
                logger.warning(
                    "Company identity race for %s; retrying in %.1fs (%d/%d)",
                    plan.filename,
                    delay,
                    attempt,
                    _MAX_LOAD_ATTEMPTS,
                )
                time.sleep(delay)
            except OperationalError:
                self._session.rollback()
                if attempt == _MAX_LOAD_ATTEMPTS:
                    raise
                delay = 0.1 * (2 ** (attempt - 1))
                logger.warning(
                    "Transient load failure for %s; retrying in %.1fs (%d/%d)",
                    plan.filename,
                    delay,
                    attempt,
                    _MAX_LOAD_ATTEMPTS,
                )
                time.sleep(delay)
        raise RuntimeError("unreachable load retry state")

    def _is_company_identity_race(self, exc: IntegrityError) -> bool:
        """Return True when *exc* is the company natural-key race condition."""
        message = str(exc).lower()
        original = str(getattr(exc, "orig", "")).lower()
        return (
            _COMPANY_IDENTITY_CONSTRAINT in message
            or _COMPANY_IDENTITY_CONSTRAINT in original
            or (
                "company.rated_entity" in original
                and "company.country_of_origin" in original
            )
        )

    def _load_data(
        self, plan: LoadPlan, audit_id: int, now: datetime
    ) -> int:
        """Write Company, CompanySnapshot, and all child records to the DB.

        Parameters
        ----------
        plan:
            The transformed LoadPlan whose data is being loaded.
        audit_id:
            Primary key of the already-flushed UploadAudit row.
        now:
            Load timestamp; used for SCD2 valid_from / valid_to columns.

        Returns
        -------
        int
            Number of data rows written (snapshot + segments + methodologies +
            metrics; the audit row itself is not counted).
        """
        # ── find or create company ────────────────────────────────────────────
        company = self._session.execute(
            select(Company)
            .where(
                Company.rated_entity == plan.rated_entity,
                Company.country_of_origin == plan.country_of_origin,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if company is None:
            company = Company(
                rated_entity=plan.rated_entity,
                corporate_sector=plan.corporate_sector,
                country_of_origin=plan.country_of_origin,
            )
            self._session.add(company)
            self._session.flush()
        elif company.corporate_sector != plan.corporate_sector:
            company.corporate_sector = plan.corporate_sector

        # ── SCD2: close current snapshot if one exists ────────────────────────
        current = self._session.execute(
            select(OrmSnapshot).where(
                OrmSnapshot.company_id == company.id,
                OrmSnapshot.is_current.is_(True),
            )
        ).scalar_one_or_none()

        if current is not None:
            current.is_current = False
            current.valid_to = now
            self._session.flush()

        max_ver = self._session.execute(
            select(func.max(OrmSnapshot.version_number)).where(
                OrmSnapshot.company_id == company.id
            )
        ).scalar()
        next_version = (max_ver or 0) + 1

        # ── create new snapshot ───────────────────────────────────────────────
        snapshot = OrmSnapshot(
            company_id=company.id,
            upload_id=audit_id,
            version_number=next_version,
            snapshot_date=now.date(),
            valid_from=now,
            valid_to=None,
            is_current=True,
            reporting_currency=plan.reporting_currency,
            accounting_principles=plan.accounting_principles,
            business_year_end=plan.business_year_end,
            segmentation_criteria=plan.segmentation_criteria,
            business_risk_profile=plan.business_risk_profile,
            blended_industry_risk_profile=plan.blended_industry_risk_profile,
            competitive_positioning=plan.competitive_positioning,
            market_share=plan.market_share,
            diversification=plan.diversification,
            operating_profitability=plan.operating_profitability,
            sector_specific_factor_1=plan.sector_specific_factor_1,
            sector_specific_factor_2=plan.sector_specific_factor_2,
            financial_risk_profile=plan.financial_risk_profile,
            leverage=plan.leverage,
            interest_cover=plan.interest_cover,
            cash_flow_cover=plan.cash_flow_cover,
            liquidity=plan.liquidity,
        )
        self._session.add(snapshot)
        self._session.flush()

        # ── child records ─────────────────────────────────────────────────────
        for seg in plan.industry_segments:
            self._session.add(
                OrmSegment(
                    snapshot_id=snapshot.id,
                    position=seg.position,
                    industry_name=seg.industry_name,
                    risk_score=seg.risk_score,
                    weight=seg.weight,
                )
            )

        for position, name in enumerate(plan.rating_methodologies, start=1):
            self._session.add(
                RatingMethodology(
                    snapshot_id=snapshot.id,
                    position=position,
                    methodology_name=name,
                )
            )

        for metric in plan.scope_metrics:
            self._session.add(
                OrmMetric(
                    snapshot_id=snapshot.id,
                    metric_name=metric.metric_name,
                    year=metric.year,
                    is_estimate=metric.is_estimate,
                    value=metric.value,
                )
            )

        return (
            1  # snapshot
            + len(plan.industry_segments)
            + len(plan.rating_methodologies)
            + len(plan.scope_metrics)
        )


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """Run the pipeline against all files in settings.data_dir.

    Called by `make pipeline` (python -m src.pipeline.pipeline).
    Exits with code 1 if any file fails so CI can detect problems.
    """
    from src.core.config import settings
    from src.core.db import session_scope

    logger.info("Pipeline starting — data_dir=%s", settings.data_dir)

    with session_scope() as session:
        pipeline = Pipeline(session)
        batch_report = pipeline.process_directory_report(settings.data_dir)
    logger.info(
        "Pipeline complete — %d succeeded, %d failed, %d duplicate, %d records, %.2fs",
        batch_report.succeeded,
        batch_report.failed,
        batch_report.duplicates,
        batch_report.records_written,
        batch_report.duration_seconds,
    )
    if batch_report.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
