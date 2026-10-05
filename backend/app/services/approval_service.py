"""Service for teacher review state transitions, approvals, rejections, and single-item regeneration."""

import datetime
from sqlalchemy.orm import Session

from backend.app.db.models.content import Item, ItemVersion
from backend.app.db.models.unit import Unit
from backend.app.db.models.source import SourceChunk
from backend.app.db.models.audit import Decision, GenerationRun
from backend.app.generation.prompts.templates import load_prompt_template, render_template
from backend.app.generation.schemas import (
    ExplanationBlock,
    ExampleStep,
    QuizQuestion,
    PracticeItem,
    RevisionPoint,
)
from backend.app.llm.base import LLMProvider


from backend.app.db.models.quality import QualityFlag
from backend.app.core.exceptions import ApprovalBlockedException


def approve_item_version(
    db: Session,
    item_version_id: str,
    note: str | None = None,
    override: bool = False,
    override_note: str | None = None,
    actor: str = "teacher",
) -> ItemVersion:
    """Approve an item version.
    
    Rule: Approval is blocked if there are unresolved high-severity quality flags,
    unless explicit override=True and an override note are provided.
    """
    ver = db.query(ItemVersion).filter_by(id=item_version_id).first()
    if not ver:
        raise ValueError(f"ItemVersion '{item_version_id}' not found.")

    if ver.status == "Approved":
        return ver  # Already approved

    # Check for unresolved high-severity quality flags
    unresolved_high_flags = (
        db.query(QualityFlag)
        .filter_by(item_version_id=ver.id, resolved=False, severity="high")
        .all()
    )

    if unresolved_high_flags and not override:
        flag_msgs = "; ".join(f.message for f in unresolved_high_flags)
        raise ApprovalBlockedException(
            f"Approval blocked due to unresolved high-severity quality flags: {flag_msgs}",
            details={"unresolved_flags": [f.id for f in unresolved_high_flags]},
        )

    ver.status = "Approved"
    ver.approved_at = datetime.datetime.now(datetime.timezone.utc)
    db.add(ver)

    item = ver.item
    item.current_approved_version_id = ver.id
    db.add(item)

    unit_id = item.asset.unit_id
    action_name = "flag_override" if (unresolved_high_flags and override) else "approve"
    decision_note = override_note or note or ("Approved with flag override" if action_name == "flag_override" else "Approved item version")

    decision = Decision(
        unit_id=unit_id,
        item_version_id=ver.id,
        action=action_name,
        actor=actor,
        note=decision_note,
    )
    db.add(decision)

    db.commit()
    db.refresh(ver)
    return ver


def reject_item_version(db: Session, item_version_id: str, note: str | None = None, actor: str = "teacher") -> ItemVersion:
    """Reject an item version. Sets status='Needs Revision', logs Decision."""
    ver = db.query(ItemVersion).filter_by(id=item_version_id).first()
    if not ver:
        raise ValueError(f"ItemVersion '{item_version_id}' not found.")

    ver.status = "Needs Revision"
    db.add(ver)

    unit_id = ver.item.asset.unit_id
    decision = Decision(
        unit_id=unit_id,
        item_version_id=ver.id,
        action="reject",
        actor=actor,
        note=note or "Rejected item version",
    )
    db.add(decision)

    db.commit()
    db.refresh(ver)
    return ver


async def regenerate_single_item(
    db: Session,
    item_id: str,
    llm_provider: LLMProvider,
    teacher_feedback: str | None = None,
    actor: str = "teacher",
) -> ItemVersion:
    """Regenerate a single item.
    
    Creates a NEW item_version with status='Draft' and version_number = max + 1.
    Rule 3.3: Regenerating one item must not modify any other item or approved version.
    """
    item = db.query(Item).filter_by(id=item_id).first()
    if not item:
        raise ValueError(f"Item '{item_id}' not found.")

    asset = item.asset
    unit = asset.unit
    latest_ver = db.query(ItemVersion).filter_by(item_id=item.id).order_by(ItemVersion.version_number.desc()).first()
    if not latest_ver:
        raise ValueError(f"Item '{item_id}' has no existing versions.")

    # Find target objective
    obj = [o for o in unit.objectives if o.id == latest_ver.objective_id or o.code == latest_ver.objective_id]
    obj_code = obj[0].code if obj else "O1"
    obj_text = obj[0].text if obj else "Objective"

    chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).order_by(SourceChunk.position).all()
    source_chunks_str = "\n".join(f"{c.chunk_label}: {c.text}" for c in chunks)

    # Gather summaries of other items in this asset to avoid duplicate stems/prompts
    other_items = [it for it in asset.items if it.id != item.id]
    existing_summaries = []
    for it in other_items:
        v = it.versions[-1]
        existing_summaries.append(str(v.content))
    existing_str = "\n".join(existing_summaries) if existing_summaries else "None"

    regen_template = load_prompt_template("single_item_regen_v1.txt")
    prompt_vars = {
        "item_type": item.item_type,
        "objective_code": obj_code,
        "objective_text": obj_text,
        "teacher_feedback": teacher_feedback or "None",
        "existing_item_summaries": existing_str,
        "target_level": unit.target_level,
        "difficulty": unit.difficulty,
        "source_chunks": source_chunks_str,
    }
    rendered_prompt = render_template(regen_template, prompt_vars)
    system_prompt = load_prompt_template("system_prompt_v1.txt")

    schema_map = {
        "explanation_block": ExplanationBlock,
        "example_step": ExampleStep,
        "mcq": QuizQuestion,
        "short_answer": PracticeItem,
        "revision_point": RevisionPoint,
    }
    target_schema = schema_map.get(item.item_type, QuizQuestion)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    new_item_obj = await llm_provider.generate_structured(
        prompt=rendered_prompt,
        schema=target_schema,
        system_prompt=system_prompt,
    )

    # Convert schema object to DB content dict
    if item.item_type == "mcq":
        content_dict = {
            "stem": new_item_obj.stem,
            "options": [opt.model_dump() for opt in new_item_obj.options],
            "correct_label": new_item_obj.correct_label,
            "rationale": new_item_obj.rationale,
        }
    elif item.item_type == "short_answer":
        content_dict = {
            "prompt": new_item_obj.prompt,
            "model_answer": new_item_obj.model_answer,
            "marking_points": new_item_obj.marking_points,
        }
    elif item.item_type == "explanation_block":
        content_dict = {"heading": new_item_obj.heading, "body": new_item_obj.body}
    elif item.item_type == "example_step":
        content_dict = {
            "step_number": new_item_obj.step_number,
            "instruction": new_item_obj.instruction,
            "working": new_item_obj.working,
            "result": new_item_obj.result,
        }
    else:
        content_dict = {"point": new_item_obj.point}

    new_version_number = latest_ver.version_number + 1
    new_ver = ItemVersion(
        item_id=item.id,
        version_number=new_version_number,
        content=content_dict,
        status="Draft",
        objective_id=latest_ver.objective_id,
        source_chunk_ids=new_item_obj.source_chunk_ids,
        bloom_level=new_item_obj.bloom_level,
        source_version_id=latest_ver.source_version_id,
        model_id=latest_ver.model_id,
        prompt_template_version="single_item_regen_v1",
    )
    db.add(new_ver)
    db.flush()

    item.latest_version_id = new_ver.id
    db.add(item)

    decision = Decision(
        unit_id=unit.id,
        item_version_id=new_ver.id,
        action="regenerate",
        actor=actor,
        note=f"Regenerated single item (v{new_version_number})",
    )
    db.add(decision)

    db.commit()
    db.refresh(new_ver)

    # Run quality guardrails automatically
    from backend.app.guardrails.runner import run_unit_guardrails
    await run_unit_guardrails(db, unit.id, llm_provider)

    return new_ver
