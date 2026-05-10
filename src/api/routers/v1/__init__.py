"""Version 1 API routers: companies, snapshots, uploads."""

from fastapi import APIRouter

from src.api.routers.v1 import companies, snapshots, uploads

router = APIRouter(prefix="/v1")
router.include_router(companies.router)
router.include_router(snapshots.router)
router.include_router(uploads.router)

__all__ = ["router"]
