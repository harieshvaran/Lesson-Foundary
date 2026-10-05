"""API endpoints for item queries, version history, review gate actions, and single-item regeneration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.db.models.content import Item, ItemVersion
from backend.app.services.approval_service import approve_item_version, reject_item_version, regenerate_single_item
from backend.app.llm.factory import get_llm_provider

router = APIRouter()


class ItemVersionResponse(BaseModel):
    id: str
    item_id: str
    version_number: int
    content: dict
    status: str
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str | None
    source_version_id: str
    model_id: str
    prompt_template_version: str
    created_at: str


class ActionRequest(BaseModel):
    note: str | None = None
    override: bool = False
    override_note: str | None = None


class RegenerateRequest(BaseModel):
    teacher_feedback: str | None = None


@router.get("/items/{id}/versions", response_model=list[ItemVersionResponse])
def get_item_versions(id: str, db: Session = Depends(get_db)):
    """Retrieve version history for an item."""
    item = db.query(Item).filter_by(id=id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{id}' not found.")

    versions = db.query(ItemVersion).filter_by(item_id=id).order_by(ItemVersion.version_number.desc()).all()
    return [
        ItemVersionResponse(
            id=v.id,
            item_id=v.item_id,
            version_number=v.version_number,
            content=v.content,
            status=v.status,
            objective_id=v.objective_id,
            source_chunk_ids=v.source_chunk_ids,
            bloom_level=v.bloom_level,
            source_version_id=v.source_version_id,
            model_id=v.model_id,
            prompt_template_version=v.prompt_template_version,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post("/item-versions/{id}/approve", response_model=ItemVersionResponse)
def approve_version(id: str, req: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    """Approve an item version. Sets status='Approved', sets current_approved_version_id, logs Decision."""
    try:
        ver = approve_item_version(db=db, item_version_id=id, note=req.note, override=req.override, override_note=req.override_note)
        return ItemVersionResponse(
            id=ver.id,
            item_id=ver.item_id,
            version_number=ver.version_number,
            content=ver.content,
            status=ver.status,
            objective_id=ver.objective_id,
            source_chunk_ids=ver.source_chunk_ids,
            bloom_level=ver.bloom_level,
            source_version_id=ver.source_version_id,
            model_id=ver.model_id,
            prompt_template_version=ver.prompt_template_version,
            created_at=ver.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/item-versions/{id}/reject", response_model=ItemVersionResponse)
def reject_version(id: str, req: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    """Reject an item version. Sets status='Needs Revision', logs Decision."""
    try:
        ver = reject_item_version(db=db, item_version_id=id, note=req.note)
        return ItemVersionResponse(
            id=ver.id,
            item_id=ver.item_id,
            version_number=ver.version_number,
            content=ver.content,
            status=ver.status,
            objective_id=ver.objective_id,
            source_chunk_ids=ver.source_chunk_ids,
            bloom_level=ver.bloom_level,
            source_version_id=ver.source_version_id,
            model_id=ver.model_id,
            prompt_template_version=ver.prompt_template_version,
            created_at=ver.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/items/{id}/regenerate", response_model=ItemVersionResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_item(id: str, req: RegenerateRequest = RegenerateRequest(), db: Session = Depends(get_db)):
    """Regenerate a single item. Creates a NEW Draft ItemVersion (vN+1), leaving all other items byte-identical."""
    try:
        provider = get_llm_provider()
        ver = await regenerate_single_item(db=db, item_id=id, llm_provider=provider, teacher_feedback=req.teacher_feedback)
        return ItemVersionResponse(
            id=ver.id,
            item_id=ver.item_id,
            version_number=ver.version_number,
            content=ver.content,
            status=ver.status,
            objective_id=ver.objective_id,
            source_chunk_ids=ver.source_chunk_ids,
            bloom_level=ver.bloom_level,
            source_version_id=ver.source_version_id,
            model_id=ver.model_id,
            prompt_template_version=ver.prompt_template_version,
            created_at=ver.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
