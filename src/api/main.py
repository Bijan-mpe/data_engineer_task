"""FastAPI application factory and default app instance."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Response, status

from src.api.dependencies import check_database_health
from src.api.routers.v1 import router as v1_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Scope Ratings Data API",
        version="0.1.0",
        description="API for company rating snapshots, upload lineage, and comparisons.",
    )
    app.include_router(v1_router)

    @app.get("/health", tags=["health"])
    async def health(
        response: Response,
        database_ok: Annotated[bool, Depends(check_database_health)],
    ) -> dict[str, str]:
        """Return application and database readiness status."""
        if not database_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unhealthy", "database": "unreachable"}
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
