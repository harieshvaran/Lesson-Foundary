"""SQLAlchemy models for teacher intent, units, objectives, and constraints."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_versions.id"), nullable=False, index=True)
    target_level: Mapped[str] = mapped_column(String(50), nullable=False, default="Grade 8")
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    objectives: Mapped[list["Objective"]] = relationship("Objective", back_populates="unit", cascade="all, delete-orphan")
    constraints: Mapped["Constraint | None"] = relationship("Constraint", back_populates="unit", uselist=False, cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="unit", cascade="all, delete-orphan")


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # O1, O2, ...
    text: Mapped[str] = mapped_column(Text, nullable=False)
    target_bloom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gap_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unchecked")  # supported | partial | unsupported | unchecked
    gap_evidence_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="objectives")


class Constraint(Base):
    __tablename__ = "constraints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("units.id"), nullable=False, unique=True)
    vocabulary_level: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    max_length_words: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    answer_reveal_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="never_in_stem")
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    unit: Mapped["Unit"] = relationship("Unit", back_populates="constraints")
