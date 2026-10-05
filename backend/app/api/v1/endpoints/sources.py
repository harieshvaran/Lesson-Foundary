"""API endpoints for source upload, chunking, and metadata retrieval."""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.db.models.source import SourceVersion, SourceChunk
from backend.app.services.source_service import create_source_version

router = APIRouter()


class SourceResponse(BaseModel):
    id: str
    source_key: str
    version_number: int
    title: str
    content_hash: str
    file_type: str
    injection_flags: dict | None
    created_at: str


class ChunkResponse(BaseModel):
    id: str
    chunk_label: str
    position: int
    text: str


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    title: str = Form(...),
    source_key: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a source text or PDF document. Parses, chunks, runs injection scan, and saves SourceVersion."""
    try:
        content_bytes = await file.read()
        source_ver = create_source_version(
            db=db,
            file_bytes=content_bytes,
            filename=file.filename or "uploaded.txt",
            title=title,
            source_key=source_key,
        )
        return SourceResponse(
            id=source_ver.id,
            source_key=source_ver.source_key,
            version_number=source_ver.version_number,
            title=source_ver.title,
            content_hash=source_ver.content_hash,
            file_type=source_ver.file_type,
            injection_flags=source_ver.injection_flags,
            created_at=source_ver.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sources/{source_key}/versions", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_new_source_version(
    source_key: str,
    file: UploadFile = File(...),
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload a new version for an existing source key."""
    try:
        content_bytes = await file.read()
        source_ver = create_source_version(
            db=db,
            file_bytes=content_bytes,
            filename=file.filename or "uploaded.txt",
            title=title,
            source_key=source_key,
        )
        return SourceResponse(
            id=source_ver.id,
            source_key=source_ver.source_key,
            version_number=source_ver.version_number,
            title=source_ver.title,
            content_hash=source_ver.content_hash,
            file_type=source_ver.file_type,
            injection_flags=source_ver.injection_flags,
            created_at=source_ver.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sources/{id}", response_model=SourceResponse)
def get_source(id: str, db: Session = Depends(get_db)):
    """Retrieve details for a source version by ID."""
    source_ver = db.query(SourceVersion).filter_by(id=id).first()
    if not source_ver:
        raise HTTPException(status_code=404, detail=f"Source version '{id}' not found.")

    return SourceResponse(
        id=source_ver.id,
        source_key=source_ver.source_key,
        version_number=source_ver.version_number,
        title=source_ver.title,
        content_hash=source_ver.content_hash,
        file_type=source_ver.file_type,
        injection_flags=source_ver.injection_flags,
        created_at=source_ver.created_at.isoformat(),
    )


@router.get("/sources/{id}/chunks", response_model=list[ChunkResponse])
def get_source_chunks(id: str, db: Session = Depends(get_db)):
    """Retrieve list of chunks for a source version."""
    chunks = db.query(SourceChunk).filter_by(source_version_id=id).order_by(SourceChunk.position).all()
    return [
        ChunkResponse(
            id=c.id,
            chunk_label=c.chunk_label,
            position=c.position,
            text=c.text,
        )
        for c in chunks
    ]
