"""API Router for API v1."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
