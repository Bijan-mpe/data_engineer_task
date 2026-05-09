"""
Corporate credit rating data platform.

Package structure:
  src.core       — configuration, database, logging, constants
  src.pipeline   — ETL: extract, validate, transform, load
  src.models     — ORM tables, pipeline DTOs, API response schemas
  src.repository — data access layer (DAO) consumed by the API
  src.api        — FastAPI application and versioned routers
"""
