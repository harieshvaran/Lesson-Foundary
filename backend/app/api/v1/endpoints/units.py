"""API endpoints for unit setup, gap checking, full pack generation, alignment matrix, and decision audit logs."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.db.models.unit import Unit
from backend.app.db.models.audit import Decision
from backend.app.services.unit_service import create_unit_with_objectives, run_unit_gap_check
from backend.app.services.generation_service import generate_quiz_asset, generate_full_pack, UnsupportedObjectiveException
from backend.app.services.alignment_service import compute_unit_alignment_matrix
from backend.app.llm.factory import get_llm_provider

router = APIRouter()


class ObjectiveCreate(BaseModel):
    code: str | None = None
    text: str
    target_bloom: str | None = None


class UnitCreateRequest(BaseModel):
    title: str
    source_version_id: str
    objectives: list[ObjectiveCreate]
    target_level: str = "Grade 8"
    difficulty: str = "medium"
    vocabulary_level: str = "standard"
    max_length_words: int = 500
    answer_reveal_policy: str = "never_in_stem"
    style_notes: str | None = None


class ObjectiveResponse(BaseModel):
    id: str
    code: str
    text: str
    target_bloom: str | None
    gap_status: str
    gap_evidence_chunk_ids: list[str] | None


class SourceStatusResponse(BaseModel):
    current_version_number: int
    latest_version_number: int
    is_outdated: bool
    badge: str


class UnitResponse(BaseModel):
    id: str
    title: str
    source_version_id: str
    target_level: str
    difficulty: str
    objectives: list[ObjectiveResponse]
    source_status: SourceStatusResponse | None = None


class QuizGenerateRequest(BaseModel):
    num_questions: int = 4
    confirm_partial: bool = False


class DecisionResponse(BaseModel):
    id: str
    unit_id: str
    item_version_id: str | None
    action: str
    actor: str
    note: str | None
    created_at: str


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(req: UnitCreateRequest, db: Session = Depends(get_db)):
    """Create a new learning unit tied to a source version with at least 2 objectives."""
    try:
        obj_dicts = [o.model_dump() for o in req.objectives]
        unit = create_unit_with_objectives(
            db=db,
            title=req.title,
            source_version_id=req.source_version_id,
            objectives_data=obj_dicts,
            target_level=req.target_level,
            difficulty=req.difficulty,
            vocabulary_level=req.vocabulary_level,
            max_length_words=req.max_length_words,
            answer_reveal_policy=req.answer_reveal_policy,
            style_notes=req.style_notes,
        )

        objs_resp = [
            ObjectiveResponse(
                id=o.id,
                code=o.code,
                text=o.text,
                target_bloom=o.target_bloom,
                gap_status=o.gap_status,
                gap_evidence_chunk_ids=o.gap_evidence_chunk_ids,
            )
            for o in unit.objectives
        ]

        from backend.app.db.models.source import SourceVersion
        src_ver = db.query(SourceVersion).filter_by(id=unit.source_version_id).first()
        status_resp = None
        if src_ver:
            latest_src = (
                db.query(SourceVersion)
                .filter_by(source_key=src_ver.source_key)
                .order_by(SourceVersion.version_number.desc())
                .first()
            )
            is_outdated = (latest_src.version_number > src_ver.version_number) if latest_src else False
            status_resp = SourceStatusResponse(
                current_version_number=src_ver.version_number,
                latest_version_number=latest_src.version_number if latest_src else src_ver.version_number,
                is_outdated=is_outdated,
                badge=f"generated from v{src_ver.version_number}, source is now v{latest_src.version_number}" if is_outdated else f"generated from v{src_ver.version_number}",
            )

        return UnitResponse(
            id=unit.id,
            title=unit.title,
            source_version_id=unit.source_version_id,
            target_level=unit.target_level,
            difficulty=unit.difficulty,
            objectives=objs_resp,
            source_status=status_resp,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/units/{id}", response_model=UnitResponse)
def get_unit(id: str, db: Session = Depends(get_db)):
    """Retrieve details for a unit by ID."""
    unit = db.query(Unit).filter_by(id=id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{id}' not found.")

    objs_resp = [
        ObjectiveResponse(
            id=o.id,
            code=o.code,
            text=o.text,
            target_bloom=o.target_bloom,
            gap_status=o.gap_status,
            gap_evidence_chunk_ids=o.gap_evidence_chunk_ids,
        )
        for o in unit.objectives
    ]

    from backend.app.db.models.source import SourceVersion
    src_ver = db.query(SourceVersion).filter_by(id=unit.source_version_id).first()
    status_resp = None
    if src_ver:
        latest_src = (
            db.query(SourceVersion)
            .filter_by(source_key=src_ver.source_key)
            .order_by(SourceVersion.version_number.desc())
            .first()
        )
        is_outdated = (latest_src.version_number > src_ver.version_number) if latest_src else False
        status_resp = SourceStatusResponse(
            current_version_number=src_ver.version_number,
            latest_version_number=latest_src.version_number if latest_src else src_ver.version_number,
            is_outdated=is_outdated,
            badge=f"generated from v{src_ver.version_number}, source is now v{latest_src.version_number}" if is_outdated else f"generated from v{src_ver.version_number}",
        )

    return UnitResponse(
        id=unit.id,
        title=unit.title,
        source_version_id=unit.source_version_id,
        target_level=unit.target_level,
        difficulty=unit.difficulty,
        objectives=objs_resp,
        source_status=status_resp,
    )


@router.post("/units/{id}/gap-check", response_model=list[ObjectiveResponse])
async def execute_gap_check(id: str, db: Session = Depends(get_db)):
    """Run model-based gap check across all unit objectives."""
    try:
        provider = get_llm_provider()
        updated_objs = await run_unit_gap_check(db=db, unit_id=id, llm_provider=provider)
        return [
            ObjectiveResponse(
                id=o.id,
                code=o.code,
                text=o.text,
                target_bloom=o.target_bloom,
                gap_status=o.gap_status,
                gap_evidence_chunk_ids=o.gap_evidence_chunk_ids,
            )
            for o in updated_objs
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/units/{id}/generate-quiz", status_code=status.HTTP_201_CREATED)
async def generate_quiz(id: str, req: QuizGenerateRequest = QuizGenerateRequest(), db: Session = Depends(get_db)):
    """Generate quiz asset for unit. Unsupported objectives block generation with HTTP 400."""
    try:
        provider = get_llm_provider()
        asset = await generate_quiz_asset(
            db=db,
            unit_id=id,
            llm_provider=provider,
            num_questions=req.num_questions,
            confirm_partial=req.confirm_partial,
        )
        return {
            "asset_id": asset.id,
            "unit_id": asset.unit_id,
            "asset_type": asset.asset_type,
            "item_count": len(asset.items),
            "status": "success",
        }
    except UnsupportedObjectiveException as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_objective",
                "message": e.message,
                "details": e.details,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/units/{id}/generate-pack", status_code=status.HTTP_201_CREATED)
async def generate_pack(id: str, confirm_partial: bool = False, db: Session = Depends(get_db)):
    """Generate all 5 artifacts as one aligned unit."""
    try:
        provider = get_llm_provider()
        assets = await generate_full_pack(db=db, unit_id=id, llm_provider=provider, confirm_partial=confirm_partial)
        return {
            "unit_id": id,
            "assets_generated": len(assets),
            "asset_types": [a.asset_type for a in assets],
            "status": "success",
        }
    except UnsupportedObjectiveException as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "unsupported_objective",
                "message": e.message,
                "details": e.details,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/units/{id}/alignment")
def get_unit_alignment(id: str, db: Session = Depends(get_db)):
    """Retrieve objective x asset alignment matrix and imbalance warnings."""
    try:
        return compute_unit_alignment_matrix(db, id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/units/{id}/decisions", response_model=list[DecisionResponse])
def get_unit_decisions(id: str, db: Session = Depends(get_db)):
    """Retrieve decision audit history for a unit."""
    decisions = db.query(Decision).filter_by(unit_id=id).order_by(Decision.created_at.desc()).all()
    return [
        DecisionResponse(
            id=d.id,
            unit_id=d.unit_id,
            item_version_id=d.item_version_id,
            action=d.action,
            actor=d.actor,
            note=d.note,
            created_at=d.created_at.isoformat(),
        )
        for d in decisions
    ]
