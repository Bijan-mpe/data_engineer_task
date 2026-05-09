"""Unit tests for src.core.constants — enum completeness and ordering."""

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


def test_master_sheet_name_constant():
    assert MASTER_SHEET_NAME == "MASTER"


def test_data_file_extension_constant():
    assert DATA_FILE_EXTENSION == ".xlsm"


def test_master_field_contains_required_fields():
    """All field labels needed by the extractor must be present as enum members."""
    required = {
        "Rated entity",
        "CorporateSector",
        "Rating methodologies applied",
        "Industry risk",
        "Industry risk score",
        "Industry weight",
        "Reporting Currency/Units",
        "Country of origin",
        "Accounting principles",
        "End of business year",
    }
    assert required.issubset({f.value for f in MasterField})


def test_accounting_principles_ifrs():
    assert AccountingPrinciples.IFRS.value == "IFRS"


def test_business_year_end_complete_set():
    """All twelve calendar months must be present with correct string values."""
    assert {e.value for e in BusinessYearEnd} == {
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    }


def test_rating_grade_complete_scale():
    """The exact set of valid Scope rating grades — no additions, no omissions."""
    assert {g.value for g in RatingGrade} == {
        "AAA",
        "AA+", "AA", "AA-",
        "A+", "A", "A-",
        "BBB+", "BBB", "BBB-",
        "BB+", "BB", "BB-",
        "B+", "B", "B-",
        # these values are not in excel file but exist in full a scope score grade. 
        "CCC+", "CCC", "CCC-",
        "CC", "C",
        "SD", "D",
    }

# Note: There is no need of the test  
def test_rating_grade_sd_positioned_between_c_and_d():
    """SD (Selective Default) must sit immediately between C and D in declaration order."""
    grades = [g.value for g in RatingGrade]
    assert grades.index("SD") == grades.index("C") + 1
    assert grades.index("D") == grades.index("SD") + 1


def test_pipeline_status_complete_set():
    assert {s.value for s in PipelineStatus} == {"pending", "running", "success", "failed", "duplicate", "skipped"}


def test_liquidity_score_complete_set():
    assert {s.value for s in LiquidityScore} == {
        "+2 notches", "+1 notch", "Adequate", "-1 notch", "-2 notches",
    }
