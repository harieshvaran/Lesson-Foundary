"""SQLAlchemy models for generation runs and teacher decisions audit log."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, JSON, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False, index=True)
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success | failed | invalid_output
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed', 'invalid_output')", name="check_generation_run_status"),
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False, index=True)
    item_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("item_versions.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # approve | reject | regenerate | flag_override | bloom_override | flag_resolve | source_update
    actor: Mapped[str] = mapped_column(String(50), nullable=False, default="teacher")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
