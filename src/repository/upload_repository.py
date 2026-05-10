"""Upload repository: read-only access to upload audit rows and metrics."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.constants import PipelineStatus
from src.models.orm import UploadAudit
from src.models.responses import UploadStatsResponse
from src.repository.pagination import validate_pagination


class UploadRepository:
    """Queries for upload audit listing, detail, statistics, and source files."""

    def __init__(self, session: Session, data_dir: Path | None = None) -> None:
        """Create a repository bound to an existing session and optional data dir."""
        self._session = session
        self._data_dir = data_dir

    def list_uploads(self, *, limit: int = 100, offset: int = 0) -> list[UploadAudit]:
        """Return upload audit rows ordered newest first."""
        limit, offset = validate_pagination(limit, offset)
        statement = (
            select(UploadAudit)
            .order_by(
                UploadAudit.created_at.desc(),
                UploadAudit.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(statement).scalars().all())

    def get_upload(self, upload_id: int) -> UploadAudit | None:
        """Return one upload audit row by primary key, or None when absent."""
        return self._session.get(UploadAudit, upload_id)

    def get_stats(self) -> UploadStatsResponse:
        """Return aggregate upload counts for the uploads stats endpoint."""
        total_uploads = self._count()
        successful = self._count(PipelineStatus.SUCCESS)
        failed = self._count(PipelineStatus.FAILED)
        duplicates_skipped = self._count(PipelineStatus.DUPLICATE)
        skipped = self._count(PipelineStatus.SKIPPED)
        total_records = self._total_records()
        return UploadStatsResponse(
            total_uploads=total_uploads,
            successful=successful,
            failed=failed,
            duplicates_skipped=duplicates_skipped,
            skipped=skipped,
            total_records=total_records,
        )

    def get_source_file_path(self, upload_id: int) -> Path | None:
        """Return the source file path for an upload when it exists on disk."""
        if self._data_dir is None:
            return None
        upload = self.get_upload(upload_id)
        if upload is None:
            return None
        data_dir = self._data_dir.resolve()
        path = (data_dir / upload.filename).resolve()
        if not path.is_relative_to(data_dir):
            return None
        return path if path.is_file() else None

    def _count(self, status: PipelineStatus | None = None) -> int:
        """Count upload rows, optionally limited to one status."""
        statement = select(func.count()).select_from(UploadAudit)
        if status is not None:
            statement = statement.where(UploadAudit.status == status)
        return int(self._session.execute(statement).scalar_one())

    def _total_records(self) -> int:
        """Return the sum of successful upload record counts."""
        statement = select(func.coalesce(func.sum(UploadAudit.record_count), 0)).where(
            UploadAudit.status == PipelineStatus.SUCCESS
        )
        return int(self._session.execute(statement).scalar_one())
