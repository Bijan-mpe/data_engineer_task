"""
FastAPI application package.

Modules:
  main     — application factory: creates the FastAPI instance and registers routers
  routers  — versioned route handlers (v1/)
"""

from src.api.main import app, create_app

__all__ = ["app", "create_app"]
