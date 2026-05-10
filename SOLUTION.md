# Solution - Corporate Credit Rating Data Pipeline

This document explains the implemented solution, how to run it, and the main
engineering assumptions. The original assignment text is kept in `README.md`.

## Overview

The project ingests the `MASTER` sheet from macro-enabled Excel workbooks,
validates the extracted credit-rating data, loads it into a temporal warehouse,
and serves analytical reads through FastAPI.

The implemented flow is:

```text
Extract -> Validate -> Transform -> Load -> Serve
```

## Document Structure

```text
README.md                         # original assignment / requirements
SOLUTION.md                       # implementation explanation and runbook
AI_USAGE.md                       # required AI disclosure
docs/
  CODEX_CHAT.md                   # Codex conversation log
  CLAUDE_CHAT.md                  # Claude conversation log
  architecture/
    data_model.md                 # warehouse model and ERD notes
  samples/
    sample_api_calls.md           # API examples and response snippets
    data_quality_report_example.md
    data_pipeline_log_example.jsonl
  openapi/
    swagger.json                  # generated OpenAPI artifact
```

## Architecture

The code is layered by responsibility:

- `src/core`: settings, SQLAlchemy engine/session helpers, logging, constants.
- `src/models`: SQLAlchemy ORM models, pipeline DTOs, API response models.
- `src/pipeline`: Excel extraction, validation, transformation, and loading.
- `src/repository`: DAO/query layer used by the API.
- `src/api`: FastAPI app, dependency wiring, and `/v1` routers.
- `alembic`: PostgreSQL schema migrations.
- `tests/unit` and `tests/integration`: local unit checks plus service-backed
  integration tests.

The warehouse model is documented in
`docs/architecture/data_model.md`.

## Data Model Summary

The core warehouse tables are:

- `upload_audit`: file-level lineage, file hash, status, timing, record counts,
  and failure details.
- `company`: stable company identity keyed by rated entity and country.
- `company_snapshot`: one versioned snapshot per successful file load, with
  SCD Type 2 validity columns.
- `industry_segment`, `rating_methodology`, `scope_metric`: child tables for
  repeated workbook sections.

The model supports:

- historical file submissions,
- point-in-time comparison,
- per-company history,
- multiple versions per company,
- lineage back to the source workbook.

## API Design

The assignment lists unversioned endpoint requirements. The implementation uses
versioned API routes under `/v1` and adds `/health` for container readiness.

Implemented endpoints:

- `GET /v1/companies`
- `GET /v1/companies/{company_id}`
- `GET /v1/companies/{company_id}/versions`
- `GET /v1/companies/{company_id}/history`
- `GET /v1/companies/compare`
- `GET /v1/snapshots`
- `GET /v1/snapshots/latest`
- `GET /v1/snapshots/{snapshot_id}`
- `GET /v1/uploads`
- `GET /v1/uploads/stats`
- `GET /v1/uploads/{upload_id}/details`
- `GET /v1/uploads/{upload_id}/file`
- `GET /health`

Sample calls and responses are in
`docs/samples/sample_api_calls.md`.

## Running Locally

Install dependencies:

```bash
make install
```

Run the API in development mode:

```bash
make dev
```

Run the ETL pipeline against `DATA_DIR`:

```bash
make pipeline
```

Apply database migrations:

```bash
make migrate
```

## Running with Docker Compose

Start PostgreSQL and the API:

```bash
docker compose up -d
```

The Compose flow:

- starts PostgreSQL 16 with a persistent named volume,
- waits for PostgreSQL health,
- runs Alembic migrations in the API container,
- optionally runs the ETL pipeline over `/app/data`,
- starts Uvicorn on port `8000`,
- exposes `/health` for readiness,
- writes JSON data-quality reports to `/app/reports`.

Relevant environment settings:

- `DATA_DIR`: source workbook directory.
- `QUALITY_REPORT_DIR`: output directory for generated pipeline quality reports.
- `RUN_PIPELINE_ON_STARTUP`: when `true`, the API container runs the pipeline at
  startup.
- `SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_MAX_OVERFLOW`,
  `SQLALCHEMY_POOL_TIMEOUT`, `SQLALCHEMY_POOL_RECYCLE`: SQLAlchemy engine pool
  tuning.

The source `data/` directory is mounted read-only. Compose mounts `./reports`
at `/app/reports` so generated quality reports survive container restarts.

Repeated container restarts can add duplicate audit rows for duplicate files.
Set `RUN_PIPELINE_ON_STARTUP=false` after seeding if API restarts should leave
upload statistics unchanged.

## Data Quality Reports

`Pipeline.process_directory_report(..., report_dir=...)` returns a
`PipelineBatchReport` and writes a JSON report when `report_dir` is provided.
The CLI uses `QUALITY_REPORT_DIR`, which defaults to `./reports`.

An example report is in
`docs/samples/data_quality_report_example.md`.

## Tests

Run all tests:

```bash
make test
```

Run unit tests only:

```bash
make test-unit
```

Run integration tests:

```bash
make test-integration
```

PostgreSQL integration tests are skipped unless `POSTGRES_TEST_DATABASE_URL` is
set to a disposable PostgreSQL database. Those tests apply Alembic migrations
and exercise PostgreSQL-specific behavior.

## OpenAPI / Swagger

FastAPI serves interactive Swagger UI at:

```text
http://localhost:8000/docs
```
FastAPI serves Redoc UI at:

```text
http://localhost:8000/redoc
```

The generated OpenAPI artifact:

```text
docs/openapi/swagger.json
```

## Implementation Assumptions and Considerations

- The expected operating model is one pipeline instance running at a time. Some
  concurrent-run risks are handled, but running multiple pipeline instances
  against the same database and shared `data/` volume should be reviewed more
  deeply before production use.
- Idempotency is currently based on file content hash. If analysts need to load
  identical file content as a separate business event or test case, a key based
  on filename plus file content may be more appropriate.
- The API currently uses synchronous SQLAlchemy with FastAPI. This is
  acceptable for the assignment, but a production async API should either use
  synchronous route handlers so FastAPI can run blocking database work in a
  threadpool, or migrate the database layer to SQLAlchemy's async engine with
  `AsyncSession`.

## Future Improvements

- Expand the data-quality report beyond the current run totals and per-file
  validation errors. Useful additions include extraction-failure categories,
  load-failure categories, audit-write failures, warning counts, validity
  rates, and rule-level completeness metrics.
- Add a production monitoring stack, such as Prometheus and Grafana, for
  metrics, dashboards, and alerting.
- Add a full Docker Compose E2E acceptance test that brings up PostgreSQL and the
  API, runs Alembic migrations, loads the real workbooks, and queries the live
  API.
- Add pagination metadata envelopes for list endpoints if client requirements
  grow. Current list endpoints support `limit` and `offset`, but return plain
  arrays without total counts or next/previous metadata.
