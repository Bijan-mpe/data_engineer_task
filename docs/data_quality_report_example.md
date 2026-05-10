# Data Quality Report Example

The pipeline now writes a JSON data-quality report for each directory run when
`report_dir` is provided, and the CLI writes reports under `QUALITY_REPORT_DIR`
(`./reports` by default). This static document mirrors the report shape from a
successful load of the four assignment workbooks. Timestamps are illustrative.

## Generated JSON Report

```json
{
  "started_at": "2026-05-10T17:57:06.387319Z",
  "finished_at": "2026-05-10T17:57:06.825572Z",
  "duration_seconds": 0.438253,
  "files_found": 4,
  "reports": [
    {
      "filename": "corporates_A_1.xlsm",
      "status": "success",
      "company_name": "Company A",
      "validation": {
        "filename": "corporates_A_1.xlsm",
        "is_valid": true,
        "errors": []
      },
      "error_message": null,
      "records_written": 64
    },
    {
      "filename": "corporates_A_2.xlsm",
      "status": "success",
      "company_name": "Company A",
      "validation": {
        "filename": "corporates_A_2.xlsm",
        "is_valid": true,
        "errors": []
      },
      "error_message": null,
      "records_written": 63
    },
    {
      "filename": "corporates_B_1.xlsm",
      "status": "success",
      "company_name": "Company B",
      "validation": {
        "filename": "corporates_B_1.xlsm",
        "is_valid": true,
        "errors": []
      },
      "error_message": null,
      "records_written": 64
    },
    {
      "filename": "corporates_B_2.xlsm",
      "status": "success",
      "company_name": "Company B",
      "validation": {
        "filename": "corporates_B_2.xlsm",
        "is_valid": true,
        "errors": []
      },
      "error_message": null,
      "records_written": 64
    }
  ],
  "succeeded": 4,
  "failed": 0,
  "duplicates": 0,
  "records_written": 255,
  "validation_error_count": 0
}
```

## Per-File Summary

| File | Company | Status | Version | Validation errors | Records written |
| --- | --- | --- | ---: | ---: | ---: |
| `corporates_A_1.xlsm` | Company A | success | 1 | 0 | 64 |
| `corporates_A_2.xlsm` | Company A | success | 2 | 0 | 63 |
| `corporates_B_1.xlsm` | Company B | success | 1 | 0 | 64 |
| `corporates_B_2.xlsm` | Company B | success | 2 | 0 | 64 |

## Fixture Data Facts

| Company | Sector | Country | Currency | Metrics per workbook |
| --- | --- | --- | --- | ---: |
| Company A | Personal & Household Goods | Federal Republic of Germany | EUR | 60 |
| Company B | Automobiles & Parts | Swiss Confederation | CHF | 60 |

## Quality Checks

| Check | Result | Notes |
| --- | --- | --- |
| MASTER sheet present | pass | All four workbooks contain the required sheet. |
| Required identity fields | pass | Rated entity, sector, country, and currency are present. |
| Rating grades valid | pass | Extracted grade values match the supported Scope rating scale. |
| Industry weights valid | pass | Segment weights are numeric and sum to 1.0 per file. |
| Accounting principles valid | pass | Values match the allowed accounting-principle list. |
| Liquidity values valid | pass | Liquidity values match the expected notch/adequacy scale. |
| Scope metrics valid | pass | Each workbook produces 60 metric rows. |
| Idempotency | pass | Re-running an already successful file is marked duplicate. |

## Example Failed-File Shape

```json
{
  "filename": "bad_workbook.xlsm",
  "status": "failed",
  "company_name": null,
  "validation": {
    "filename": "bad_workbook.xlsm",
    "is_valid": false,
    "errors": [
      {
        "field": "rated_entity",
        "raw_value": null,
        "message": "required field is missing"
      },
      {
        "field": "industry_segments",
        "raw_value": [],
        "message": "industry weights must sum to 1.0"
      }
    ]
  },
  "error_message": "rated_entity: required field is missing",
  "records_written": 0
}
```
