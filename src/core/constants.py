"""
Shared constants and enumerations for the corporate credit rating pipeline.

All magic strings that appear in Excel source files or the database schema are
defined here so that typos are caught at import time rather than at runtime.
"""

from enum import Enum

MASTER_SHEET_NAME = "MASTER"
DATA_FILE_EXTENSION = ".xlsm"


class MasterField(str, Enum):
    """Field labels as they appear verbatim in column B of the MASTER sheet.

    The MASTER sheet uses a key-value layout: column B holds these labels,
    column C holds the primary value.  Some fields (Industry risk, Industry
    weight, Rating methodologies) may span additional columns for multi-segment
    companies.
    """

    RATED_ENTITY = "Rated entity"
    CORPORATE_SECTOR = "CorporateSector"
    RATING_METHODOLOGIES = "Rating methodologies applied"
    INDUSTRY_RISK = "Industry risk"
    INDUSTRY_RISK_SCORE = "Industry risk score"
    INDUSTRY_WEIGHT = "Industry weight"
    SEGMENTATION_CRITERIA = "Segmentation criteria"
    REPORTING_CURRENCY = "Reporting Currency/Units"
    COUNTRY_OF_ORIGIN = "Country of origin"
    ACCOUNTING_PRINCIPLES = "Accounting principles"
    BUSINESS_YEAR_END = "End of business year"
    BUSINESS_RISK_PROFILE = "Business risk profile"
    BLENDED_INDUSTRY_RISK_PROFILE = "(Blended) Industry risk profile"
    COMPETITIVE_POSITIONING = "Competitive Positioning"
    MARKET_SHARE = "Market share"
    DIVERSIFICATION = "Diversification"
    OPERATING_PROFITABILITY = "Operating profitability"
    SECTOR_SPECIFIC_1 = "Sector/company-specific factors (1)"
    SECTOR_SPECIFIC_2 = "Sector/company-specific factors (2)"
    FINANCIAL_RISK_PROFILE = "Financial risk profile"
    LEVERAGE = "Leverage"
    INTEREST_COVER = "Interest cover"
    CASH_FLOW_COVER = "Cash flow cover"
    LIQUIDITY = "Liquidity"
    SCOPE_CREDIT_METRICS = "[Scope Credit Metrics]"


class AccountingPrinciples(str, Enum):
    """Accounting standard applied by the rated entity."""

    IFRS = "IFRS"
    US_GAAP = "US GAAP"
    LOCAL_GAAP = "Local GAAP"


class BusinessYearEnd(str, Enum):
    """Month in which the entity's fiscal year closes."""

    JANUARY = "January"
    FEBRUARY = "February"
    MARCH = "March"
    APRIL = "April"
    MAY = "May"
    JUNE = "June"
    JULY = "July"
    AUGUST = "August"
    SEPTEMBER = "September"
    OCTOBER = "October"
    NOVEMBER = "November"
    DECEMBER = "December"


class RatingGrade(str, Enum):
    """Scope credit rating grades from highest (AAA) to default (D).

    Covers the full investment-grade and speculative-grade scale including
    notch variants (+/-) and the Selective Default (SD) category.
    """

    AAA = "AAA"
    AA_PLUS = "AA+"
    AA = "AA"
    AA_MINUS = "AA-"
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    BBB_PLUS = "BBB+"
    BBB = "BBB"
    BBB_MINUS = "BBB-"
    BB_PLUS = "BB+"
    BB = "BB"
    BB_MINUS = "BB-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    # "CCC+", "CCC", "CCC-" values are not in excel file but exist in full a scope score grade.
    CCC_PLUS = "CCC+"
    CCC = "CCC"
    CCC_MINUS = "CCC-"
    CC = "CC"
    C = "C"
    SD = "SD"
    D = "D"


class PipelineStatus(str, Enum):
    """Execution state of a pipeline run, persisted to the upload audit table."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"


class LiquidityScore(str, Enum):
    """Liquidity notch adjustment values as they appear in the MASTER sheet.

    Liquidity is expressed as a notch adjustment relative to the financial
    risk profile, ranging from +2 (very strong) to -2 (weak).  The string
    format matches the Excel source exactly (e.g. "+1 notch", "-2 notches").
    """

    PLUS_2 = "+2 notches"
    PLUS_1 = "+1 notch"
    ADEQUATE = "Adequate"
    MINUS_1 = "-1 notch"
    MINUS_2 = "-2 notches"
