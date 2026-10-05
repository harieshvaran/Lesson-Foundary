"""API Router for API v1."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, sources, units, items, quality, student

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(sources.router, tags=["Sources"])
api_router.include_router(units.router, tags=["Units"])
api_router.include_router(items.router, tags=["Items"])
api_router.include_router(quality.router, tags=["Quality"])
api_router.include_router(student.router, tags=["Student"])

