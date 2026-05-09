"""Shared pytest fixtures for unit tests."""

from collections.abc import Callable
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from src.models.schemas import RawMasterData

# Fixed timestamp used by snapshot fixtures — exposed as now_utc fixture for assertions.
_SNAPSHOT_DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def now_utc() -> datetime:
    """Fixed UTC datetime shared across snapshot fixtures."""
    return _SNAPSHOT_DT


@pytest.fixture
def make_company_ns() -> Callable[..., SimpleNamespace]:
    """Factory for ORM-like company SimpleNamespace objects.

    Usage: make_company_ns() or make_company_ns(rated_entity="Company B")
    """
    def _factory(**overrides) -> SimpleNamespace:
        attrs = dict(
            id=1,
            rated_entity="Company A",
            corporate_sector="Personal & Household Goods",
            country_of_origin="Federal Republic of Germany",
        )
        attrs.update(overrides)
        return SimpleNamespace(**attrs)
    return _factory


@pytest.fixture
def make_snapshot_ns() -> Callable[..., SimpleNamespace]:
    """Factory for ORM-like snapshot summary SimpleNamespace objects.

    Includes SCD2 fields (valid_from, valid_to, is_current) and the
    denormalised company identity fields added to SnapshotSummaryResponse.
    Usage: make_snapshot_ns() or make_snapshot_ns(business_risk_profile="BBB")
    """
    def _factory(**overrides) -> SimpleNamespace:
        attrs = dict(
            id=1,
            company_id=1,
            upload_id=1,
            version_number=1,
            snapshot_date=date(2024, 1, 1),
            valid_from=_SNAPSHOT_DT,
            valid_to=None,
            is_current=True,
            rated_entity="Company A",
            corporate_sector="Personal & Household Goods",
            country_of_origin="Federal Republic of Germany",
            reporting_currency="EUR",
            business_risk_profile="B+",
            financial_risk_profile="C",
            liquidity="-2 notches",
        )
        attrs.update(overrides)
        return SimpleNamespace(**attrs)
    return _factory


@pytest.fixture
def make_raw_master_dict() -> Callable[..., dict]:
    """Factory for minimal valid RawMasterData keyword-argument dicts.

    Returns a function so individual tests can override specific fields:
        make_raw_master_dict(rating_methodologies=[])
    """
    def _factory(**overrides) -> dict:
        base: dict = {
            "rated_entity": "Company A",
            "corporate_sector": "Personal & Household Goods",
            "rating_methodologies": ["General Corporate Rating Methodology"],
            "industry_segments": [
                {
                    "position": 1,
                    "industry_name": "Consumer Products: Non-Discretionary",
                    "risk_score": "A",
                    "weight": 1.0,
                }
            ],
            "reporting_currency": "EUR",
            "country_of_origin": "Federal Republic of Germany",
            "accounting_principles": "IFRS",
            "business_year_end": "December",
            "business_risk_profile": "B+",
            "blended_industry_risk_profile": "A",
            "competitive_positioning": "B+",
            "market_share": "BB-",
            "diversification": "B+",
            "operating_profitability": "BB-",
            "financial_risk_profile": "C",
            "leverage": "CCC",
            "interest_cover": "B-",
            "cash_flow_cover": "CCC",
            "liquidity": "-2 notches",
            "scope_metrics": [
                {
                    "metric_name": "Scope-adjusted EBITDA interest cover",
                    "year": 2023,
                    "value": 4.862,
                }
            ],
        }
        base.update(overrides)
        return base
    return _factory


@pytest.fixture
def raw_master_data(make_raw_master_dict) -> RawMasterData:
    """Minimal valid RawMasterData instance representing Company A."""
    return RawMasterData(**make_raw_master_dict())
