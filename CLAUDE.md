# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Senior Data Engineer assignment: build a production-ready pipeline that ingests `.xlsm` Excel files, models corporate credit-rating metadata in a PostgreSQL data warehouse, exposes it through a FastAPI REST API, and packages everything with Docker Compose. No code exists yet — only source data in `data/` and the spec in `README.md`.

## Commands

```bash
make install          # install all dependencies (requirements-dev.txt)
make dev              # run FastAPI dev server on port 8000 with hot reload
make pipeline         # run the ETL pipeline
make test             # run all tests
make test-unit        # run unit tests only
make test-integration # run integration tests only
make test-cov         # run tests with HTML coverage report
make lint             # ruff check
make format           # ruff format
make migrate          # alembic upgrade head
make migrate-down     # alembic downgrade -1
make docker-up        # docker-compose up -d
make docker-down      # docker-compose down
```

Run a single test file: `pytest tests/unit/test_imports.py -v`

## Architecture

The solution must follow this layered design:

**Extract → Validate → Transform → Load → Serve**

### Key design decisions from the spec

- **Excel parsing**: Only the `MASTER` sheet is used. It has a non-standard key-value structure (40 rows × 13 columns) with `Unnamed: 0–12` headers — column 1 holds field labels, column 2 holds values. Requires custom row-by-row parsing, not `pd.read_excel` with default headers.
- **Data model**: Star schema in PostgreSQL. The central fact is a `company_snapshot` (one row per file upload per company). Slowly Changing Dimension Type 2 on company metadata. Separate `upload_audit` table tracking source file, timestamp, and lineage.
- **Version control**: Files `corporates_A_1` and `corporates_A_2` represent the same company at two versions; the model must handle multiple versions per company without duplicates on re-run (idempotent loads keyed on source filename).
- **Pipeline state**: Track which files have been processed so incremental runs skip already-loaded files.
- **API**: FastAPI with Pydantic models. Endpoints must support point-in-time queries (`as_of_date`), time-series history per company, and multi-company comparison. Full OpenAPI docs auto-generated.
- **Containerization**: Two services — `postgres` (PostgreSQL 15+, schema-init on first run, health check) and `api` (depends on postgres health, mounts `data/` volume, port 8000).

### Module layout

```
src/
  core/
    config.py         # pydantic-settings: reads .env into Settings object
    constants.py      # shared enums and literals
    db.py             # SQLAlchemy engine + session factory (used by pipeline and API)
    logging.py        # logger setup
  pipeline/
    extractor.py      # MASTER sheet parsing from .xlsm (openpyxl, row-by-row KV parsing)
    validator.py      # field presence, type, range checks (weights sum to 1.0, etc.)
    pipeline.py       # Pipeline class: extract / validate / transform / load as methods
  models/
    orm.py            # SQLAlchemy ORM table definitions
    schemas.py        # Pydantic models for pipeline internal data flow (DTOs)
    responses.py      # Pydantic models for API response bodies
  repository/
    company_repository.py   # DAO for company / dimension queries
    snapshot_repository.py  # DAO for snapshot fact queries
    upload_repository.py    # DAO for upload audit queries
  api/
    main.py           # FastAPI app + router registration
    routers/
      v1/
        companies.py
        snapshots.py
        uploads.py
alembic/
  versions/           # migration scripts (alembic convention)
  env.py
alembic.ini
tests/
  unit/
  integration/
  conftest.py
data/                 # source .xlsm files — do not modify
docker-compose.yml
Dockerfile
Makefile
.env.example
requirements.txt
requirements-dev.txt
pyproject.toml        # pytest + ruff config
```

## Implementation steps

Work is done one step at a time. Never move to the next step without explicit user confirmation. Each step must include its own unit tests, and all tests must pass before the step is considered done.

| # | Step | Status |
|---|------|--------|
| 1 | Project structure + dependencies + Makefile | ✅ Done |
| 2 | Core — config, database, logging, constants | |
| 3 | ERD + Pydantic schemas (`models/schemas.py`, `models/responses.py`) | |
| 4 | SQLAlchemy ORM models (`models/orm.py`) | |
| 5 | Alembic migrations | |
| 6 | Extractor (`pipeline/extractor.py`) | |
| 7 | Validator (`pipeline/validator.py`) | |
| 8 | Pipeline class (`pipeline/pipeline.py` — extract/validate/transform/load methods) | |
| 9 | Repository / DAO layer (`repository/`) | |
| 10 | FastAPI (`api/main.py` + `routers/v1/`) | |
| 11 | Docker + Docker Compose | |
| 12 | Integration & E2E tests + sample outputs | |

## Data files

| File | Company | Version | Notable difference |
|------|---------|---------|-------------------|
| `corporates_A_1.xlsm` | Company A | v1 | Industry risk = A |
| `corporates_A_2.xlsm` | Company A | v2 | Industry risk = BBB |
| `corporates_B_1.xlsm` | Company B | v1 | Original weights |
| `corporates_B_2.xlsm` | Company B | v2 | Changed weights |

## Deliverables checklist (from spec)

- [ ] Working `docker-compose up -d` that seeds the DB and starts the API
- [ ] ETL pipeline that processes all 4 files idempotently
- [ ] All 8 API endpoint groups implemented with OpenAPI docs at `/docs`
- [ ] Data quality report generated per pipeline run
- [ ] ≥10 sample API call examples with responses
- [ ] Unit + integration tests
- [ ] `AI_USAGE.md` completed honestly
