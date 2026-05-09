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
| file_hash | TEXT | SHA-256; idempotency key; indexed |
| status | PipelineStatus | pending / running / success / failed / duplicate / skipped |
| error_message | TEXT | nullable |
| created_at | TIMESTAMPTZ | server default now() |
| processed_at | TIMESTAMPTZ | nullable |
| record_count | INT | nullable |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

## company

Stable identity dimension. Fields that change between file versions
(currency, accounting principles, year-end) live in `company_snapshot`,
not here.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| rated_entity | TEXT | indexed |
| corporate_sector | TEXT | |
| country_of_origin | TEXT | |
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

## company_snapshot (SCD Type 2)

One row per source file × company. Each new file version for the same
company inserts a new row; the previous row's `valid_to` is closed.
`is_current` is a convenience shortcut for `WHERE valid_to IS NULL`.

`version_number` is application-managed: the pipeline computes
`MAX(version_number) WHERE company_id = ?` + 1 inside the load transaction.
A unique constraint on `(company_id, version_number)` enforces correctness
at the database level.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| company_id | INT FK | → company.id |
| upload_id | INT FK | → upload_audit.id |
| version_number | INT | per-company counter; (company_id, version_number) unique |
| snapshot_date | DATE | |
| valid_from | TIMESTAMPTZ | set on first load |
| valid_to | TIMESTAMPTZ | nullable — NULL = currently active |
| is_current | BOOL | shortcut for WHERE valid_to IS NULL; indexed |
| reporting_currency | VARCHAR(10) | |
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
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

**Indexes:** `(company_id, is_current)` composite; `is_current` single-column;
`UNIQUE (company_id) WHERE is_current = true` partial (PostgreSQL) — prevents two current snapshots for the same company without blocking historical rows

**Constraints:** `UNIQUE (company_id, version_number)`

## industry_segment

Multi-value child of `company_snapshot`. Multi-segment companies have one
row per segment column in the MASTER sheet.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| snapshot_id | INT FK | → company_snapshot.id |
| position | INT | 1-indexed column order |
| industry_name | TEXT | |
| risk_score | VARCHAR(5) | RatingGrade value |
| weight | FLOAT | |
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

**Constraints:** `UNIQUE (snapshot_id, position)`

## rating_methodology

Multi-value child of `company_snapshot`.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| snapshot_id | INT FK | → company_snapshot.id |
| position | INT | |
| methodology_name | TEXT | |
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

**Constraints:** `UNIQUE (snapshot_id, position)`

## scope_metric

Time-series financial metrics from the `[Scope Credit Metrics]` section.
One row per metric × year. `is_estimate` distinguishes actuals from
forward estimates (e.g. "2026E" in the source). `value` is NULL when the
source cell contains "No data".

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| snapshot_id | INT FK | → company_snapshot.id |
| metric_name | TEXT | |
| year | INT | |
| is_estimate | BOOL | |
| value | FLOAT | nullable |
| created_at | TIMESTAMPTZ | server default now() |
| updated_at | TIMESTAMPTZ | server default now(); updated on every ORM write |

**Constraints:** `UNIQUE (snapshot_id, metric_name, year, is_estimate)`
