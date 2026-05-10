# Sample API Calls

These examples assume the application is running at `http://localhost:8000`
after loading the four assignment workbooks. IDs and timestamps are examples
from a fresh local load; primary keys can differ if the database already has
rows.

## 1. Health Check

```bash
curl -s http://localhost:8000/health
```

```json
{"status":"ok","database":"ok"}
```

## 2. List Companies

```bash
curl -s "http://localhost:8000/v1/companies?limit=10&offset=0"
```

```json
[
  {
    "id": 1,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany"
  },
  {
    "id": 2,
    "rated_entity": "Company B",
    "corporate_sector": "Automobiles & Parts",
    "country_of_origin": "Swiss Confederation"
  }
]
```

## 3. Get Company

```bash
curl -s http://localhost:8000/v1/companies/1
```

```json
{
  "id": 1,
  "rated_entity": "Company A",
  "corporate_sector": "Personal & Household Goods",
  "country_of_origin": "Federal Republic of Germany"
}
```

## 4. Company Versions

```bash
curl -s http://localhost:8000/v1/companies/1/versions
```

```json
[
  {
    "id": 1,
    "company_id": 1,
    "upload_id": 1,
    "version_number": 1,
    "snapshot_date": "2026-05-10",
    "valid_from": "2026-05-10T17:57:06.387440",
    "valid_to": "2026-05-10T17:57:06.493039",
    "is_current": false,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany",
    "reporting_currency": "EUR",
    "business_risk_profile": "B+",
    "financial_risk_profile": "C",
    "liquidity": "-2 notches"
  },
  {
    "id": 2,
    "company_id": 1,
    "upload_id": 2,
    "version_number": 2,
    "snapshot_date": "2026-05-10",
    "valid_from": "2026-05-10T17:57:06.493039",
    "valid_to": null,
    "is_current": true,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany",
    "reporting_currency": "EUR",
    "business_risk_profile": "B",
    "financial_risk_profile": "CC",
    "liquidity": "-2 notches"
  }
]
```

## 5. Company History

```bash
curl -s http://localhost:8000/v1/companies/1/history
```

```json
{
  "company": {
    "id": 1,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany"
  },
  "snapshots": [
    {
      "id": 1,
      "company_id": 1,
      "upload_id": 1,
      "version_number": 1,
      "snapshot_date": "2026-05-10",
      "valid_from": "2026-05-10T17:57:06.387440",
      "valid_to": "2026-05-10T17:57:06.493039",
      "is_current": false,
      "rated_entity": "Company A",
      "corporate_sector": "Personal & Household Goods",
      "country_of_origin": "Federal Republic of Germany",
      "reporting_currency": "EUR",
      "business_risk_profile": "B+",
      "financial_risk_profile": "C",
      "liquidity": "-2 notches"
    }
  ]
}
```

## 6. Compare Companies as of a Date

```bash
curl -s "http://localhost:8000/v1/companies/compare?company_ids=1&company_ids=2&as_of_date=2026-05-10"
```

```json
{
  "companies": [
    {
      "id": 1,
      "rated_entity": "Company A",
      "corporate_sector": "Personal & Household Goods",
      "country_of_origin": "Federal Republic of Germany"
    },
    {
      "id": 2,
      "rated_entity": "Company B",
      "corporate_sector": "Automobiles & Parts",
      "country_of_origin": "Swiss Confederation"
    }
  ],
  "snapshots": [
    {
      "id": 2,
      "company_id": 1,
      "upload_id": 2,
      "version_number": 2,
      "snapshot_date": "2026-05-10",
      "valid_from": "2026-05-10T17:57:06.493039",
      "valid_to": null,
      "is_current": true,
      "rated_entity": "Company A",
      "corporate_sector": "Personal & Household Goods",
      "country_of_origin": "Federal Republic of Germany",
      "reporting_currency": "EUR",
      "business_risk_profile": "B",
      "financial_risk_profile": "CC",
      "liquidity": "-2 notches"
    },
    {
      "id": 4,
      "company_id": 2,
      "upload_id": 4,
      "version_number": 2,
      "snapshot_date": "2026-05-10",
      "valid_from": "2026-05-10T17:57:06.744988",
      "valid_to": null,
      "is_current": true,
      "rated_entity": "Company B",
      "corporate_sector": "Automobiles & Parts",
      "country_of_origin": "Swiss Confederation",
      "reporting_currency": "CHF",
      "business_risk_profile": "BBB-",
      "financial_risk_profile": "BB",
      "liquidity": "+1 notch"
    }
  ]
}
```

## 7. List Snapshots with Filters

```bash
curl -s "http://localhost:8000/v1/snapshots?sector=Personal%20%26%20Household%20Goods&currency=EUR&limit=10"
```

```json
[
  {
    "id": 2,
    "company_id": 1,
    "upload_id": 2,
    "version_number": 2,
    "snapshot_date": "2026-05-10",
    "valid_from": "2026-05-10T17:57:06.493039",
    "valid_to": null,
    "is_current": true,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany",
    "reporting_currency": "EUR",
    "business_risk_profile": "B",
    "financial_risk_profile": "CC",
    "liquidity": "-2 notches"
  }
]
```

## 8. Latest Snapshots

```bash
curl -s http://localhost:8000/v1/snapshots/latest
```

```json
[
  {
    "id": 2,
    "company_id": 1,
    "upload_id": 2,
    "version_number": 2,
    "snapshot_date": "2026-05-10",
    "valid_from": "2026-05-10T17:57:06.493039",
    "valid_to": null,
    "is_current": true,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany",
    "reporting_currency": "EUR",
    "business_risk_profile": "B",
    "financial_risk_profile": "CC",
    "liquidity": "-2 notches"
  },
  {
    "id": 4,
    "company_id": 2,
    "upload_id": 4,
    "version_number": 2,
    "snapshot_date": "2026-05-10",
    "valid_from": "2026-05-10T17:57:06.744988",
    "valid_to": null,
    "is_current": true,
    "rated_entity": "Company B",
    "corporate_sector": "Automobiles & Parts",
    "country_of_origin": "Swiss Confederation",
    "reporting_currency": "CHF",
    "business_risk_profile": "BBB-",
    "financial_risk_profile": "BB",
    "liquidity": "+1 notch"
  }
]
```

## 9. Snapshot Detail

```bash
curl -s http://localhost:8000/v1/snapshots/2
```

```json
{
  "id": 2,
  "company": {
    "id": 1,
    "rated_entity": "Company A",
    "corporate_sector": "Personal & Household Goods",
    "country_of_origin": "Federal Republic of Germany"
  },
  "version_number": 2,
  "snapshot_date": "2026-05-10",
  "valid_from": "2026-05-10T17:57:06.493039",
  "valid_to": null,
  "is_current": true,
  "reporting_currency": "EUR",
  "accounting_principles": "IFRS",
  "business_year_end": "December",
  "segmentation_criteria": "EBITDA contribution",
  "business_risk_profile": "B",
  "blended_industry_risk_profile": "A",
  "competitive_positioning": "B+",
  "market_share": "B+",
  "diversification": "B+",
  "operating_profitability": "B",
  "sector_specific_factor_1": "B-",
  "sector_specific_factor_2": null,
  "financial_risk_profile": "CC",
  "leverage": "CCC",
  "interest_cover": "B-",
  "cash_flow_cover": "CCC",
  "liquidity": "-2 notches",
  "industry_segments": [
    {
      "position": 1,
      "industry_name": "Consumer Products: Non-Discretionary",
      "risk_score": "BBB",
      "weight": 1.0
    }
  ],
  "rating_methodologies": [
    {
      "position": 1,
      "methodology_name": "General Corporate Rating Methodology"
    }
  ],
  "scope_metrics": [
    {
      "metric_name": "Liquidity",
      "year": 2018,
      "is_estimate": false,
      "value": 4.862
    }
  ]
}
```

The real detail endpoint returns all 60 `scope_metrics` rows for this snapshot;
the response above keeps one representative row to make the example readable.

## 10. List Upload Audits

```bash
curl -s "http://localhost:8000/v1/uploads?limit=10&offset=0"
```

```json
[
  {
    "id": 1,
    "filename": "corporates_A_1.xlsm",
    "file_hash": "04bf22f57e2b75c4701c429d2ab988ed1d2bf86f29b5944b3d87185c2c7ee09b",
    "status": "success",
    "created_at": "2026-05-10T17:57:06",
    "processed_at": "2026-05-10T17:57:06.387440",
    "record_count": 64,
    "error_message": null
  }
]
```

## 11. Upload Statistics

```bash
curl -s http://localhost:8000/v1/uploads/stats
```

```json
{
  "total_uploads": 4,
  "successful": 4,
  "failed": 0,
  "duplicates_skipped": 0,
  "skipped": 0,
  "total_records": 255
}
```

## 12. Upload Details

```bash
curl -s http://localhost:8000/v1/uploads/1/details
```

```json
{
  "id": 1,
  "filename": "corporates_A_1.xlsm",
  "file_hash": "04bf22f57e2b75c4701c429d2ab988ed1d2bf86f29b5944b3d87185c2c7ee09b",
  "status": "success",
  "created_at": "2026-05-10T17:57:06",
  "processed_at": "2026-05-10T17:57:06.387440",
  "record_count": 64,
  "error_message": null
}
```

## 13. Download Source Workbook

```bash
curl -OJ http://localhost:8000/v1/uploads/1/file
```

```http
HTTP/1.1 200 OK
content-disposition: attachment; filename="corporates_A_1.xlsm"
content-type: application/vnd.ms-excel.sheet.macroEnabled.12
```
