# Data Model — Star Schema ERD

Six tables underpin the data warehouse.

## upload_audit

Tracks every pipeline run against a source file. `file_hash` (SHA-256) is
the idempotency key — a file with the same hash is skipped as a duplicate.
`filename` is not unique because the same filename may arrive with different
content across runs.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | auto-incrementing int; readable in logs |
| filename | TEXT | not unique |
| file_hash | TEXT | SHA-256; idempotency key |
| status | PipelineStatus | pending / running / success / failed / duplicate / skipped |
| error_message | TEXT | nullable |
| created_at | TIMESTAMPTZ | |
| processed_at | TIMESTAMPTZ | nullable |
| record_count | INT | nullable |

## company

Stable identity dimension. Fields that change between file versions
(currency, accounting principles, year-end) live in `company_snapshot`,
not here.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| rated_entity | TEXT | |
| corporate_sector | TEXT | |
| country_of_origin | TEXT | |

## company_snapshot (SCD Type 2)

One row per source file × company. Each new file version for the same
company inserts a new row; the previous row's `valid_to` is closed.
`is_current` is a convenience shortcut for `WHERE valid_to IS NULL`.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| company_id | UUID FK | → company.id |
| upload_id | INT FK | → upload_audit.id |
| snapshot_date | DATE | |
| valid_from | TIMESTAMPTZ | set on first load |
| valid_to | TIMESTAMPTZ | nullable — NULL = currently active |
| is_current | BOOL | shortcut for WHERE valid_to IS NULL |
| reporting_currency | TEXT | |
| accounting_principles | AccountingPrinciples | |
| business_year_end | BusinessYearEnd | |
| segmentation_criteria | TEXT | nullable |
| business_risk_profile | RatingGrade | |
| blended_industry_risk_profile | RatingGrade | |
| competitive_positioning | RatingGrade | |
| market_share | RatingGrade | |
| diversification | RatingGrade | |
| operating_profitability | RatingGrade | |
| sector_specific_factor_1 | RatingGrade | nullable |
| sector_specific_factor_2 | RatingGrade | nullable |
| financial_risk_profile | RatingGrade | |
| leverage | RatingGrade | |
| interest_cover | RatingGrade | |
| cash_flow_cover | RatingGrade | |
| liquidity | LiquidityScore | |

## industry_segment

Multi-value child of `company_snapshot`. Multi-segment companies have one
row per segment column in the MASTER sheet.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| snapshot_id | UUID FK | → company_snapshot.id |
| position | INT | 1-indexed column order |
| industry_name | TEXT | |
| risk_score | TEXT | RatingGrade value |
| weight | FLOAT | |

## rating_methodology

Multi-value child of `company_snapshot`.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| snapshot_id | UUID FK | → company_snapshot.id |
| position | INT | |
| methodology_name | TEXT | |

## scope_metric

Time-series financial metrics from the `[Scope Credit Metrics]` section.
One row per metric × year. `is_estimate` distinguishes actuals from
forward estimates (e.g. "2026E" in the source). `value` is NULL when the
source cell contains "No data".

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| snapshot_id | UUID FK | → company_snapshot.id |
| metric_name | TEXT | |
| year | INT | |
| is_estimate | BOOL | |
| value | FLOAT | nullable |
