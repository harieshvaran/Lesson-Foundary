"""SQLAlchemy models for source documents and text chunks."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class SourceVersion(Base):
    __tablename__ = "source_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="txt")
    injection_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    chunks: Mapped[list["SourceChunk"]] = relationship("SourceChunk", back_populates="source_version", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_versions.id"), nullable=False, index=True)
    chunk_label: Mapped[str] = mapped_column(String(20), nullable=False)  # S1, S2, etc.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    source_version: Mapped["SourceVersion"] = relationship("SourceVersion", back_populates="chunks")
