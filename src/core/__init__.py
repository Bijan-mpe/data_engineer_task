"""
Core infrastructure: configuration, database session management, logging, and constants.

Public API — preferred import style for consumers:

    from src.core import settings, get_logger, get_session, Base

Re-exporting from this package root decouples call sites from the internal
file layout.  If a module is renamed or split, only this file changes.
"""

from src.core.config import Settings, settings
from src.core.constants import (
    DATA_FILE_EXTENSION,
    MASTER_SHEET_NAME,
    AccountingPrinciples,
    BusinessYearEnd,
    LiquidityScore,
    MasterField,
    PipelineStatus,
    RatingGrade,
)
from src.core.db import Base, SessionFactory, engine, get_session
from src.core.logging import get_logger, setup_logging

__all__ = [
    # config
    "Settings",
    "settings",
    # db
    "Base",
    "engine",
    "SessionFactory",
    "get_session",
    # logging
    "get_logger",
    "setup_logging",
    # constants
    "MASTER_SHEET_NAME",
    "DATA_FILE_EXTENSION",
    "MasterField",
    "AccountingPrinciples",
    "BusinessYearEnd",
    "RatingGrade",
    "PipelineStatus",
    "LiquidityScore",
]
