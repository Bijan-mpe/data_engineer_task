"""Snapshot API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.responses import SnapshotDetailResponse, SnapshotSummaryResponse
from src.repository import SnapshotRepository

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("", response_model=list[SnapshotSummaryResponse])
async def list_snapshots(
    session: Annotated[Session, Depends(get_db_session)],
    company_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sector: str | None = None,
    country: str | None = None,
    currency: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SnapshotSummaryResponse]:
    """List snapshots with optional BI filters."""
    snapshots = SnapshotRepository(session).list_snapshots(
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        sector=sector,
        country=country,
        currency=currency,
        limit=limit,
        offset=offset,
    )
    return [SnapshotSummaryResponse.model_validate(snapshot) for snapshot in snapshots]


@router.get("/latest", response_model=list[SnapshotSummaryResponse])
async def get_latest_snapshots(
    session: Annotated[Session, Depends(get_db_session)],
) -> list[SnapshotSummaryResponse]:
    """Return the latest/current snapshot for each company."""
    snapshots = SnapshotRepository(session).get_latest_for_each_company()
    return [SnapshotSummaryResponse.model_validate(snapshot) for snapshot in snapshots]


@router.get("/{snapshot_id}", response_model=SnapshotDetailResponse)
async def get_snapshot(
    snapshot_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> SnapshotDetailResponse:
    """Return one snapshot with all child detail rows."""
    snapshot = SnapshotRepository(session).get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return SnapshotDetailResponse.model_validate(snapshot)
