"""Service for source ingestion, chunking, injection scanning, and versioning."""

import uuid
from sqlalchemy.orm import Session
from backend.app.db.models.source import SourceVersion, SourceChunk
from backend.app.ingestion.parser import parse_document
from backend.app.ingestion.chunker import chunk_text, compute_content_hash
from backend.app.ingestion.injection import scan_for_prompt_injection


def create_source_version(
    db: Session,
    file_bytes: bytes,
    filename: str,
    title: str,
    source_key: str | None = None,
) -> SourceVersion:
    """Ingest document, parse, compute hash, run injection scan, chunk, and save SourceVersion."""
    raw_text, file_type = parse_document(file_bytes, filename)
    content_hash = compute_content_hash(raw_text)

    # Determine key and version number
    if not source_key:
        source_key = f"src_{uuid.uuid4().hex[:10]}"

    existing_versions = db.query(SourceVersion).filter_by(source_key=source_key).all()
    version_number = len(existing_versions) + 1

    # Run injection scan
    injection_flags = scan_for_prompt_injection(raw_text)

    # Create SourceVersion record
    source_ver = SourceVersion(
        source_key=source_key,
        version_number=version_number,
        title=title,
        raw_text=raw_text,
        content_hash=content_hash,
        file_type=file_type,
        injection_flags=injection_flags,
    )
    db.add(source_ver)
    db.flush()  # get source_ver.id

    # Create SourceChunk records
    raw_chunks = chunk_text(raw_text)
    for c in raw_chunks:
        chunk = SourceChunk(
            source_version_id=source_ver.id,
            chunk_label=c["chunk_label"],
            position=c["position"],
            text=c["text"],
        )
        db.add(chunk)

    db.commit()
    db.refresh(source_ver)
    return source_ver
