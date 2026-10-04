"""SQLAlchemy models for assets, items, and item versions."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, JSON, DateTime, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # explanation | example | quiz | practice_easy | practice_advanced | revision

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="assets")
    items: Mapped[list["Item"]] = relationship("Item", back_populates="asset", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)  # explanation_block | example_step | mcq | short_answer | revision_point
    current_approved_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    latest_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="items")
    versions: Mapped[list["ItemVersion"]] = relationship("ItemVersion", back_populates="item", cascade="all, delete-orphan", foreign_keys="[ItemVersion.item_id]")


class ItemVersion(Base):
    __tablename__ = "item_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("items.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Draft")  # Draft | Approved | Needs Revision

    # Mandatory Provenance Fields (Rule 2.5: objective_id NOT NULL, source_chunk_ids non-empty)
    objective_id: Mapped[str] = mapped_column(String(36), ForeignKey("objectives.id"), nullable=False, index=True)
    source_chunk_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # validated in service layer to be non-empty list

    bloom_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bloom_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_versions.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generation_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("generation_runs.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="versions", foreign_keys=[item_id])

    __table_args__ = (
        CheckConstraint("status IN ('Draft', 'Approved', 'Needs Revision')", name="check_item_version_status"),
    )
