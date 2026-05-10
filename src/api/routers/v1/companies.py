"""Company API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.responses import (
    CompanyHistoryResponse,
    CompanyResponse,
    CompareResponse,
    SnapshotSummaryResponse,
)
from src.repository import CompanyRepository, CompareCompaniesNotFoundError

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CompanyResponse]:
    """List companies with stable company metadata."""
    companies = CompanyRepository(session).list_companies(limit=limit, offset=offset)
    return [CompanyResponse.model_validate(company) for company in companies]


@router.get("/compare", response_model=CompareResponse)
async def compare_companies(
    session: Annotated[Session, Depends(get_db_session)],
    company_ids: Annotated[list[int], Query(min_length=1)],
    as_of_date: date,
) -> CompareResponse:
    """Compare companies at a specific calendar date."""
    repository = CompanyRepository(session)
    try:
        snapshots = repository.compare_companies(company_ids, as_of_date)
    except CompareCompaniesNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "No point-in-time snapshot found for one or more companies",
                "missing_company_ids": exc.missing_company_ids,
            },
        ) from exc

    companies = [snapshot.company for snapshot in snapshots]
    return CompareResponse(
        companies=[CompanyResponse.model_validate(company) for company in companies],
        snapshots=[
            SnapshotSummaryResponse.model_validate(snapshot) for snapshot in snapshots
        ],
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyResponse:
    """Return one company by id."""
    company = CompanyRepository(session).get_company(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.get("/{company_id}/versions", response_model=list[SnapshotSummaryResponse])
async def get_company_versions(
    company_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> list[SnapshotSummaryResponse]:
    """Return all versioned snapshots for one company."""
    snapshots = CompanyRepository(session).get_versions(company_id)
    if not snapshots and CompanyRepository(session).get_company(company_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return [SnapshotSummaryResponse.model_validate(snapshot) for snapshot in snapshots]


@router.get("/{company_id}/history", response_model=CompanyHistoryResponse)
async def get_company_history(
    company_id: int,
    session: Annotated[Session, Depends(get_db_session)],
) -> CompanyHistoryResponse:
    """Return chronological snapshot history for one company."""
    repository = CompanyRepository(session)
    company = repository.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    snapshots = repository.get_history(company_id)
    return CompanyHistoryResponse(
        company=CompanyResponse.model_validate(company),
        snapshots=[
            SnapshotSummaryResponse.model_validate(snapshot) for snapshot in snapshots
        ],
    )
