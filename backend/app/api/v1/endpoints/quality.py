"""API endpoints for quality guardrail flag retrieval and resolution."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.db.models.unit import Unit
from backend.app.db.models.content import Item, ItemVersion, Asset
from backend.app.db.models.quality import QualityFlag
from backend.app.db.models.audit import Decision

router = APIRouter()


class QualityFlagResponse(BaseModel):
    id: str
    item_version_id: str
    flag_type: str
    severity: str
    message: str
    suggested_fix: str | None
    detected_by: str
    resolved: bool
    resolution_note: str | None
    created_at: str


class ResolveFlagRequest(BaseModel):
    note: str | None = None


@router.get("/units/{id}/flags", response_model=list[QualityFlagResponse])
def get_unit_quality_flags(id: str, db: Session = Depends(get_db)):
    """Retrieve quality guardrail flags for all item versions in a unit."""
    unit = db.query(Unit).filter_by(id=id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{id}' not found.")

    assets = db.query(Asset).filter_by(unit_id=id).all()
    item_ids = [it.id for a in assets for it in a.items]
    item_ver_ids = [v.id for a in assets for it in a.items for v in it.versions]

    flags = (
        db.query(QualityFlag)
        .filter(QualityFlag.item_version_id.in_(item_ver_ids))
        .order_by(QualityFlag.created_at.desc())
        .all()
    )

    return [
        QualityFlagResponse(
            id=f.id,
            item_version_id=f.item_version_id,
            flag_type=f.flag_type,
            severity=f.severity,
            message=f.message,
            suggested_fix=f.suggested_fix,
            detected_by=f.detected_by,
            resolved=f.resolved,
            resolution_note=f.resolution_note,
            created_at=f.created_at.isoformat(),
        )
        for f in flags
    ]


@router.post("/quality-flags/{id}/resolve", response_model=QualityFlagResponse)
def resolve_quality_flag(id: str, req: ResolveFlagRequest = ResolveFlagRequest(), db: Session = Depends(get_db)):
    """Resolve a quality guardrail flag and log a Decision."""
    flag = db.query(QualityFlag).filter_by(id=id).first()
    if not flag:
        raise HTTPException(status_code=404, detail=f"QualityFlag '{id}' not found.")

    flag.resolved = True
    flag.resolution_note = req.note or "Resolved by teacher"
    db.add(flag)

    ver = db.query(ItemVersion).filter_by(id=flag.item_version_id).first()
    if ver:
        unit_id = ver.item.asset.unit_id
        decision = Decision(
            unit_id=unit_id,
            item_version_id=ver.id,
            action="flag_resolve",
            actor="teacher",
            note=f"Resolved flag '{flag.flag_type}': {flag.resolution_note}",
        )
        db.add(decision)

    db.commit()
    db.refresh(flag)

    return QualityFlagResponse(
        id=flag.id,
        item_version_id=flag.item_version_id,
        flag_type=flag.flag_type,
        severity=flag.severity,
        message=flag.message,
        suggested_fix=flag.suggested_fix,
        detected_by=flag.detected_by,
        resolved=flag.resolved,
        resolution_note=flag.resolution_note,
        created_at=flag.created_at.isoformat(),
    )
