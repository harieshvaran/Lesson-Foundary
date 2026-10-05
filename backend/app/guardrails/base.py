"""Data models for guardrail findings."""

from pydantic import BaseModel


class QualityFlagData(BaseModel):
    item_version_id: str
    flag_type: str
    severity: str  # low | medium | high
    message: str
    suggested_fix: str | None = None
    detected_by: str = "deterministic"  # deterministic | llm
