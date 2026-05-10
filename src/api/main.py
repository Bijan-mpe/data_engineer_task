"""FastAPI application factory and default app instance."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers.v1 import router as v1_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Scope Ratings Data API",
        version="0.1.0",
        description="API for company rating snapshots, upload lineage, and comparisons.",
    )
    app.include_router(v1_router)
    return app


app = create_app()
