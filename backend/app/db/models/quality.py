"""SQLAlchemy models for quality guardrail flags."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class QualityFlag(Base):
    __tablename__ = "quality_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("item_versions.id"), nullable=False, index=True)
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # low | medium | high
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_by: Mapped[str] = mapped_column(String(50), nullable=False, default="deterministic")  # deterministic | llm
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high')", name="check_quality_flag_severity"),
    )
