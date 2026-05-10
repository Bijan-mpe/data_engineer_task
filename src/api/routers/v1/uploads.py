"""Upload audit API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session, get_settings
from src.core.config import Settings
from src.models.responses import UploadAuditResponse, UploadStatsResponse
from src.repository import UploadRepository

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("", response_model=list[UploadAuditResponse])
async def list_uploads(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UploadAuditResponse]:
    """List upload audit rows."""
    uploads = UploadRepository(session).list_uploads(limit=limit, offset=offset)
    return [UploadAuditResponse.model_validate(upload) for upload in uploads]


@router.get("/stats", response_model=UploadStatsResponse)
async def get_upload_stats(
    session: Annotated[Session, Depends(get_db_session)],
) -> UploadStatsResponse:
    """Return aggregate upload statistics."""
    return UploadRepository(session).get_stats()


@router.get("/{upload_id}/details", response_model=UploadAuditResponse)
async def get_upload_details(
    upload_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> UploadAuditResponse:
    """Return details for one upload audit row."""
    upload = UploadRepository(session).get_upload(upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    return UploadAuditResponse.model_validate(upload)


@router.get("/{upload_id}/file", response_class=FileResponse)
async def get_upload_file(
    upload_id: int,
    session: Annotated[Session, Depends(get_db_session)],
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Return the source file for one upload audit row."""
    repository = UploadRepository(session, app_settings.data_dir)
    path = repository.get_source_file_path(upload_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(path, filename=path.name)
