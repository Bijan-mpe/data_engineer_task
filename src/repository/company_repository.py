"""Company repository: read-only data access for company-centric views."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models.orm import Company
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.repository.pagination import validate_pagination
from src.repository.snapshot_repository import SnapshotRepository


class CompareCompaniesNotFoundError(LookupError):
    """Raised when a strict comparison cannot resolve all requested snapshots."""

    def __init__(self, missing_company_ids: list[int]) -> None:
        """Create an error that exposes the unresolved company ids."""
        self.missing_company_ids = missing_company_ids
        ids = ", ".join(str(company_id) for company_id in missing_company_ids)
        super().__init__(f"No point-in-time snapshot found for company ids: {ids}")


class CompanyRepository:
    """Queries for the company dimension and company-scoped snapshot history."""

    def __init__(self, session: Session) -> None:
        """Create a repository bound to an existing SQLAlchemy session."""
        self._session = session
        self._snapshots = SnapshotRepository(session)

    def list_companies(self, *, limit: int = 100, offset: int = 0) -> list[Company]:
        """Return all companies ordered by display name and id."""
        limit, offset = validate_pagination(limit, offset)
        statement = (
            select(Company)
            .order_by(Company.rated_entity, Company.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.execute(statement).scalars().all())

    def get_company(self, company_id: int) -> Company | None:
        """Return one company by primary key, or None when it does not exist."""
        return self._session.get(Company, company_id)

    def get_versions(self, company_id: int) -> list[OrmSnapshot]:
        """Return all snapshots for one company ordered by version number."""
        statement = (
            select(OrmSnapshot)
            .where(OrmSnapshot.company_id == company_id)
            .options(selectinload(OrmSnapshot.company))
            .order_by(OrmSnapshot.version_number)
        )
        return list(self._session.execute(statement).scalars().all())

    def get_history(self, company_id: int) -> list[OrmSnapshot]:
        """Return chronological snapshot history for one company."""
        statement = (
            select(OrmSnapshot)
            .where(OrmSnapshot.company_id == company_id)
            .options(selectinload(OrmSnapshot.company))
            .order_by(OrmSnapshot.valid_from, OrmSnapshot.id)
        )
        return list(self._session.execute(statement).scalars().all())

    def compare_companies(
        self, company_ids: list[int], as_of_date: date, *, require_all: bool = True
    ) -> list[OrmSnapshot]:
        """Return point-in-time snapshots for requested companies.

        By default this is strict for API use: every requested company id must
        resolve to an as-of snapshot, otherwise CompareCompaniesNotFoundError is
        raised so the API layer can return a clear client error.
        """
        snapshots: list[OrmSnapshot] = []
        missing_company_ids: list[int] = []
        for company_id in company_ids:
            snapshot = self._snapshots.get_as_of(company_id, as_of_date)
            if snapshot is not None:
                snapshots.append(snapshot)
            else:
                missing_company_ids.append(company_id)
        if require_all and missing_company_ids:
            raise CompareCompaniesNotFoundError(missing_company_ids)
        return snapshots
