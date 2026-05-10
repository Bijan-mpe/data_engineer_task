"""Snapshot repository: read-only queries for company snapshot facts."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from src.models.orm import Company
from src.models.orm import CompanySnapshot as OrmSnapshot
from src.repository.pagination import validate_pagination


class SnapshotRepository:
    """Queries for snapshot list, detail, latest, and point-in-time views."""

    def __init__(self, session: Session) -> None:
        """Create a repository bound to an existing SQLAlchemy session."""
        self._session = session

    def list_snapshots(
        self,
        *,
        company_id: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sector: str | None = None,
        country: str | None = None,
        currency: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OrmSnapshot]:
        """Return snapshots matching optional BI filters."""
        limit, offset = validate_pagination(limit, offset)
        statement = (
            select(OrmSnapshot)
            .join(OrmSnapshot.company)
            .options(selectinload(OrmSnapshot.company))
        )
        if company_id is not None:
            statement = statement.where(OrmSnapshot.company_id == company_id)
        if from_date is not None:
            statement = statement.where(OrmSnapshot.snapshot_date >= from_date)
        if to_date is not None:
            statement = statement.where(OrmSnapshot.snapshot_date <= to_date)
        if sector is not None:
            statement = statement.where(Company.corporate_sector == sector)
        if country is not None:
            statement = statement.where(Company.country_of_origin == country)
        if currency is not None:
            statement = statement.where(OrmSnapshot.reporting_currency == currency)

        statement = statement.order_by(
            Company.rated_entity,
            OrmSnapshot.version_number,
            OrmSnapshot.id,
        ).limit(limit).offset(offset)
        return list(self._session.execute(statement).scalars().all())

    def get_snapshot(self, snapshot_id: int) -> OrmSnapshot | None:
        """Return one snapshot with all detail relationships loaded."""
        statement = (
            select(OrmSnapshot)
            .where(OrmSnapshot.id == snapshot_id)
            .options(
                joinedload(OrmSnapshot.company),
                selectinload(OrmSnapshot.industry_segments),
                selectinload(OrmSnapshot.rating_methodologies),
                selectinload(OrmSnapshot.scope_metrics),
            )
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_latest_for_each_company(self) -> list[OrmSnapshot]:
        """Return the current snapshot for every company."""
        statement = (
            select(OrmSnapshot)
            .join(OrmSnapshot.company)
            .where(OrmSnapshot.is_current.is_(True))
            .options(selectinload(OrmSnapshot.company))
            .order_by(Company.rated_entity, OrmSnapshot.id)
        )
        return list(self._session.execute(statement).scalars().all())

    def get_as_of(self, company_id: int, as_of_date: date) -> OrmSnapshot | None:
        """Return the snapshot valid for a company on *as_of_date*."""
        as_of_start = datetime.combine(as_of_date, time.min, tzinfo=timezone.utc)
        as_of_end = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        statement = (
            select(OrmSnapshot)
            .where(
                OrmSnapshot.company_id == company_id,
                OrmSnapshot.valid_from <= as_of_end,
                or_(OrmSnapshot.valid_to.is_(None), OrmSnapshot.valid_to > as_of_start),
            )
            .options(selectinload(OrmSnapshot.company))
            .order_by(OrmSnapshot.valid_from.desc(), OrmSnapshot.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def count_current(self) -> int:
        """Return the number of current company snapshots."""
        statement = select(func.count()).select_from(OrmSnapshot).where(
            OrmSnapshot.is_current.is_(True)
        )
        return int(self._session.execute(statement).scalar_one())
