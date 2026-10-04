"""Health check API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database: str
    api_key_configured: bool
    llm_provider: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Health endpoint reporting DB connection status and whether an API key is configured (never returning secrets)."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    overall_status = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        database=db_status,
        api_key_configured=settings.is_api_key_configured,
        llm_provider=settings.LLM_PROVIDER,
        version=settings.VERSION,
    )
