"""Service for unit management, objective constraints, and gap checking."""

from sqlalchemy.orm import Session
from backend.app.db.models.source import SourceVersion, SourceChunk
from backend.app.db.models.unit import Unit, Objective, Constraint
from backend.app.generation.prompts.templates import load_prompt_template, render_template
from backend.app.generation.schemas import GapCheckOutput
from backend.app.generation.retrieval import retrieve_relevant_chunks
from backend.app.llm.base import LLMProvider


def create_unit_with_objectives(
    db: Session,
    title: str,
    source_version_id: str,
    objectives_data: list[dict],
    target_level: str = "Grade 8",
    difficulty: str = "medium",
    vocabulary_level: str = "standard",
    max_length_words: int = 500,
    answer_reveal_policy: str = "never_in_stem",
    style_notes: str | None = None,
) -> Unit:
    """Create a unit with at least 2 objectives and constraints."""
    if len(objectives_data) < 2:
        raise ValueError("A unit must have at least 2 objectives.")

    source_ver = db.query(SourceVersion).filter_by(id=source_version_id).first()
    if not source_ver:
        raise ValueError(f"SourceVersion with id '{source_version_id}' not found.")

    unit = Unit(
        title=title,
        source_version_id=source_version_id,
        target_level=target_level,
        difficulty=difficulty,
    )
    db.add(unit)
    db.flush()

    for idx, obj_dict in enumerate(objectives_data, 1):
        code = obj_dict.get("code", f"O{idx}")
        obj = Objective(
            unit_id=unit.id,
            code=code,
            text=obj_dict["text"],
            target_bloom=obj_dict.get("target_bloom"),
            gap_status="unchecked",
        )
        db.add(obj)

    constraint = Constraint(
        unit_id=unit.id,
        vocabulary_level=vocabulary_level,
        max_length_words=max_length_words,
        answer_reveal_policy=answer_reveal_policy,
        style_notes=style_notes,
    )
    db.add(constraint)

    db.commit()
    db.refresh(unit)
    return unit


async def run_unit_gap_check(
    db: Session,
    unit_id: str,
    llm_provider: LLMProvider,
) -> list[Objective]:
    """Run gap check for all objectives in a unit using the LLMProvider."""
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        raise ValueError(f"Unit with id '{unit_id}' not found.")

    chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).order_by(SourceChunk.position).all()
    gap_template = load_prompt_template("gap_check_v1.txt")
    system_prompt = load_prompt_template("system_prompt_v1.txt")

    updated_objectives = []
    for obj in unit.objectives:
        relevant = retrieve_relevant_chunks(chunks, obj.text, top_k=5)
        chunks_str = "\n".join(f"{c.chunk_label}: {c.text}" for c in relevant)

        prompt = render_template(
            gap_template,
            {
                "objective_code": obj.code,
                "objective_text": obj.text,
                "source_chunks": chunks_str,
            },
        )

        gap_result: GapCheckOutput = await llm_provider.generate_structured(
            prompt=prompt,
            schema=GapCheckOutput,
            system_prompt=system_prompt,
        )

        obj.gap_status = gap_result.status
        obj.gap_evidence_chunk_ids = gap_result.evidence_chunk_ids
        db.add(obj)
        updated_objectives.append(obj)

    db.commit()
    return updated_objectives
