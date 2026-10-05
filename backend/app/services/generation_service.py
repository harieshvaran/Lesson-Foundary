"""Service for full pack generation across all 5 artifacts with context chaining."""

import datetime
from sqlalchemy.orm import Session

from backend.app.db.models.unit import Unit
from backend.app.db.models.source import SourceChunk
from backend.app.db.models.content import Asset, Item, ItemVersion
from backend.app.db.models.audit import GenerationRun
from backend.app.generation.prompts.templates import load_prompt_template, render_template
from backend.app.generation.schemas import (
    ExplanationAssetOutput,
    ExampleAssetOutput,
    QuizAssetOutput,
    PracticeAssetOutput,
    RevisionAssetOutput,
)
from backend.app.llm.base import LLMProvider
from backend.app.core.exceptions import LLMProviderError, LessonFoundryException


class UnsupportedObjectiveException(LessonFoundryException):
    """Raised when generation is attempted on a unit with unsupported objectives."""
    pass


async def generate_quiz_asset(
    db: Session,
    unit_id: str,
    llm_provider: LLMProvider,
    num_questions: int = 4,
    confirm_partial: bool = False,
) -> Asset:
    """Generate standalone quiz asset for a unit."""
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        raise ValueError(f"Unit with id '{unit_id}' not found.")

    # Enforce Gap Check Gate
    unsupported_objs = [obj for obj in unit.objectives if obj.gap_status == "unsupported"]
    if unsupported_objs:
        unsupported_names = ", ".join(f"'{obj.code}: {obj.text}'" for obj in unsupported_objs)
        raise UnsupportedObjectiveException(
            f"Generation blocked because the following objective(s) are unsupported by the source: {unsupported_names}",
            details={"unsupported_objectives": [obj.code for obj in unsupported_objs]},
        )

    chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).order_by(SourceChunk.position).all()
    source_chunks_str = "\n".join(f"{c.chunk_label}: {c.text}" for c in chunks)
    objectives_block_str = "\n".join(f"- {obj.code} (ID: {obj.id}): {obj.text}" for obj in unit.objectives)
    valid_obj_map = {obj.code: obj.id for obj in unit.objectives}
    valid_obj_map.update({obj.id: obj.id for obj in unit.objectives})
    valid_chunk_labels = {c.chunk_label for c in chunks}

    constraints = unit.constraints
    prompt_variables = {
        "num_questions": num_questions,
        "target_level": unit.target_level,
        "difficulty": unit.difficulty,
        "vocabulary_level": constraints.vocabulary_level if constraints else "standard",
        "max_length_words": constraints.max_length_words if constraints else 500,
        "answer_reveal_policy": constraints.answer_reveal_policy if constraints else "never_in_stem",
        "style_notes": constraints.style_notes or "None",
        "objectives_block": objectives_block_str,
        "source_chunks": source_chunks_str,
    }

    quiz_template = load_prompt_template("quiz_v1.txt")
    system_prompt = load_prompt_template("system_prompt_v1.txt")
    rendered_prompt = render_template(quiz_template, prompt_variables)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    run_status = "failed"
    error_msg = None
    quiz_output: QuizAssetOutput | None = None

    try:
        quiz_output = await llm_provider.generate_structured(
            prompt=rendered_prompt,
            schema=QuizAssetOutput,
            system_prompt=system_prompt,
        )
        run_status = "success"
    except Exception as e:
        run_status = "failed"
        error_msg = str(e)

    run_record = GenerationRun(
        unit_id=unit.id,
        asset_type="quiz",
        status=run_status,
        attempts=1,
        error_message=error_msg,
        model_id=getattr(llm_provider, "model_id", "default-model"),
        prompt_template_version="quiz_v1",
        settings={"num_questions": num_questions},
        started_at=started_at,
        finished_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(run_record)
    db.commit()

    if run_status != "success" or not quiz_output:
        raise LLMProviderError(f"Quiz generation failed: {error_msg}")

    try:
        asset = Asset(unit_id=unit.id, asset_type="quiz")
        db.add(asset)
        db.flush()

        for pos, q in enumerate(quiz_output.questions, 1):
            target_obj_id = valid_obj_map.get(q.objective_id)
            if not target_obj_id:
                raise ValueError(f"Question {pos} cited invalid objective_id '{q.objective_id}'")
            invalid_chunks = [cid for cid in q.source_chunk_ids if cid not in valid_chunk_labels]
            if invalid_chunks:
                raise ValueError(f"Question {pos} cited invalid source_chunk_ids {invalid_chunks}")

            item = Item(asset_id=asset.id, position=pos, item_type="mcq")
            db.add(item)
            db.flush()

            content_dict = {
                "stem": q.stem,
                "options": [opt.model_dump() for opt in q.options],
                "correct_label": q.correct_label,
                "rationale": q.rationale,
            }
            item_version = ItemVersion(
                item_id=item.id,
                version_number=1,
                content=content_dict,
                status="Draft",
                objective_id=target_obj_id,
                source_chunk_ids=q.source_chunk_ids,
                bloom_level=q.bloom_level,
                source_version_id=unit.source_version_id,
                model_id=run_record.model_id,
                prompt_template_version="quiz_v1",
                generation_run_id=run_record.id,
            )
            db.add(item_version)
            db.flush()
            item.latest_version_id = item_version.id

        db.commit()
        db.refresh(asset)

        # Run quality guardrails automatically
        from backend.app.guardrails.runner import run_unit_guardrails
        await run_unit_guardrails(db, unit.id, llm_provider)

        return asset

    except Exception as exc:
        db.rollback()
        raise exc


async def generate_full_pack(
    db: Session,
    unit_id: str,
    llm_provider: LLMProvider,
    confirm_partial: bool = False,
) -> list[Asset]:
    """Generate all 5 artifacts in dependency order: explanation -> example -> quiz -> practice_easy -> practice_advanced -> revision."""
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        raise ValueError(f"Unit with id '{unit_id}' not found.")

    # 1. Enforce Gap Check Gate
    unsupported_objs = [obj for obj in unit.objectives if obj.gap_status == "unsupported"]
    if unsupported_objs:
        unsupported_names = ", ".join(f"'{obj.code}: {obj.text}'" for obj in unsupported_objs)
        raise UnsupportedObjectiveException(
            f"Generation blocked because the following objective(s) are unsupported by the source: {unsupported_names}",
            details={"unsupported_objectives": [obj.code for obj in unsupported_objs]},
        )

    chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).order_by(SourceChunk.position).all()
    source_chunks_str = "\n".join(f"{c.chunk_label}: {c.text}" for c in chunks)
    objectives_block_str = "\n".join(f"- {obj.code} (ID: {obj.id}): {obj.text}" for obj in unit.objectives)
    valid_obj_map = {obj.code: obj.id for obj in unit.objectives}
    valid_obj_map.update({obj.id: obj.id for obj in unit.objectives})
    valid_chunk_labels = {c.chunk_label for c in chunks}
    constraints = unit.constraints
    system_prompt = load_prompt_template("system_prompt_v1.txt")

    common_vars = {
        "target_level": unit.target_level,
        "difficulty": unit.difficulty,
        "vocabulary_level": constraints.vocabulary_level if constraints else "standard",
        "max_length_words": constraints.max_length_words if constraints else 500,
        "answer_reveal_policy": constraints.answer_reveal_policy if constraints else "never_in_stem",
        "style_notes": constraints.style_notes or "None",
        "objectives_block": objectives_block_str,
        "source_chunks": source_chunks_str,
    }

    created_assets: list[Asset] = []

    try:
        # Step 1: Explanation
        expl_template = load_prompt_template("explanation_v1.txt")
        expl_prompt = render_template(expl_template, common_vars)
        expl_out: ExplanationAssetOutput = await llm_provider.generate_structured(
            prompt=expl_prompt, schema=ExplanationAssetOutput, system_prompt=system_prompt
        )

        expl_asset = Asset(unit_id=unit.id, asset_type="explanation")
        db.add(expl_asset)
        db.flush()

        expl_text_summary = []
        for pos, block in enumerate(expl_out.blocks, 1):
            item = Item(asset_id=expl_asset.id, position=pos, item_type="explanation_block")
            db.add(item)
            db.flush()
            item_ver = ItemVersion(
                item_id=item.id,
                version_number=1,
                content={"heading": block.heading, "body": block.body},
                status="Draft",
                objective_id=valid_obj_map[block.objective_id],
                source_chunk_ids=block.source_chunk_ids,
                bloom_level=block.bloom_level,
                source_version_id=unit.source_version_id,
                model_id=getattr(llm_provider, "model_id", "mock-v1"),
                prompt_template_version="explanation_v1",
            )
            db.add(item_ver)
            db.flush()
            item.latest_version_id = item_ver.id
            expl_text_summary.append(f"{block.heading}: {block.body}")
        created_assets.append(expl_asset)

        # Step 2: Worked Example
        example_template = load_prompt_template("example_v1.txt")
        ex_vars = dict(common_vars)
        ex_vars["explanation_context"] = "\n".join(expl_text_summary)
        ex_vars["key_terms"] = ", ".join(expl_out.key_terms) if expl_out.key_terms else "None"
        ex_prompt = render_template(example_template, ex_vars)
        ex_out: ExampleAssetOutput = await llm_provider.generate_structured(
            prompt=ex_prompt, schema=ExampleAssetOutput, system_prompt=system_prompt
        )

        ex_asset = Asset(unit_id=unit.id, asset_type="example")
        db.add(ex_asset)
        db.flush()

        for pos, step in enumerate(ex_out.steps, 1):
            item = Item(asset_id=ex_asset.id, position=pos, item_type="example_step")
            db.add(item)
            db.flush()
            item_ver = ItemVersion(
                item_id=item.id,
                version_number=1,
                content={
                    "step_number": step.step_number,
                    "instruction": step.instruction,
                    "working": step.working,
                    "result": step.result,
                },
                status="Draft",
                objective_id=valid_obj_map[step.objective_id],
                source_chunk_ids=step.source_chunk_ids,
                bloom_level=step.bloom_level,
                source_version_id=unit.source_version_id,
                model_id=getattr(llm_provider, "model_id", "mock-v1"),
                prompt_template_version="example_v1",
            )
            db.add(item_ver)
            db.flush()
            item.latest_version_id = item_ver.id
        created_assets.append(ex_asset)

        # Step 3: Quiz with Answer Key
        quiz_template = load_prompt_template("quiz_v1.txt")
        q_vars = dict(common_vars)
        q_vars["num_questions"] = 4
        quiz_prompt = render_template(quiz_template, q_vars)
        quiz_out: QuizAssetOutput = await llm_provider.generate_structured(
            prompt=quiz_prompt, schema=QuizAssetOutput, system_prompt=system_prompt
        )

        quiz_asset = Asset(unit_id=unit.id, asset_type="quiz")
        db.add(quiz_asset)
        db.flush()

        for pos, q in enumerate(quiz_out.questions, 1):
            item = Item(asset_id=quiz_asset.id, position=pos, item_type="mcq")
            db.add(item)
            db.flush()
            item_ver = ItemVersion(
                item_id=item.id,
                version_number=1,
                content={
                    "stem": q.stem,
                    "options": [opt.model_dump() for opt in q.options],
                    "correct_label": q.correct_label,
                    "rationale": q.rationale,
                },
                status="Draft",
                objective_id=valid_obj_map[q.objective_id],
                source_chunk_ids=q.source_chunk_ids,
                bloom_level=q.bloom_level,
                source_version_id=unit.source_version_id,
                model_id=getattr(llm_provider, "model_id", "mock-v1"),
                prompt_template_version="quiz_v1",
            )
            db.add(item_ver)
            db.flush()
            item.latest_version_id = item_ver.id
        created_assets.append(quiz_asset)

        # Step 4 & 5: Practice Easy & Practice Advanced
        practice_template = load_prompt_template("practice_v1.txt")
        for difficulty_level, asset_name, def_text in [
            ("easy", "practice_easy", "Remember/Understand recall single-step"),
            ("advanced", "practice_advanced", "Apply/Analyze/Evaluate multi-step justification"),
        ]:
            p_vars = dict(common_vars)
            p_vars["num_items"] = 4
            p_vars["difficulty"] = difficulty_level
            p_vars["difficulty_definition"] = def_text
            p_vars["prior_context"] = "\n".join(expl_text_summary)
            prac_prompt = render_template(practice_template, p_vars)

            prac_out: PracticeAssetOutput = await llm_provider.generate_structured(
                prompt=prac_prompt, schema=PracticeAssetOutput, system_prompt=system_prompt
            )

            prac_asset = Asset(unit_id=unit.id, asset_type=asset_name)
            db.add(prac_asset)
            db.flush()

            for pos, pit in enumerate(prac_out.items, 1):
                item = Item(asset_id=prac_asset.id, position=pos, item_type="short_answer")
                db.add(item)
                db.flush()
                item_ver = ItemVersion(
                    item_id=item.id,
                    version_number=1,
                    content={
                        "prompt": pit.prompt,
                        "model_answer": pit.model_answer,
                        "marking_points": pit.marking_points,
                    },
                    status="Draft",
                    objective_id=valid_obj_map[pit.objective_id],
                    source_chunk_ids=pit.source_chunk_ids,
                    bloom_level=pit.bloom_level,
                    source_version_id=unit.source_version_id,
                    model_id=getattr(llm_provider, "model_id", "mock-v1"),
                    prompt_template_version="practice_v1",
                )
                db.add(item_ver)
                db.flush()
                item.latest_version_id = item_ver.id
            created_assets.append(prac_asset)

        # Step 6: Revision Sheet
        revision_template = load_prompt_template("revision_v1.txt")
        r_vars = dict(common_vars)
        r_vars["prior_context"] = "\n".join(expl_text_summary)
        rev_prompt = render_template(revision_template, r_vars)
        rev_out: RevisionAssetOutput = await llm_provider.generate_structured(
            prompt=rev_prompt, schema=RevisionAssetOutput, system_prompt=system_prompt
        )

        rev_asset = Asset(unit_id=unit.id, asset_type="revision")
        db.add(rev_asset)
        db.flush()

        for pos, point in enumerate(rev_out.points, 1):
            item = Item(asset_id=rev_asset.id, position=pos, item_type="revision_point")
            db.add(item)
            db.flush()
            item_ver = ItemVersion(
                item_id=item.id,
                version_number=1,
                content={"point": point.point},
                status="Draft",
                objective_id=valid_obj_map[point.objective_id],
                source_chunk_ids=point.source_chunk_ids,
                bloom_level=point.bloom_level,
                source_version_id=unit.source_version_id,
                model_id=getattr(llm_provider, "model_id", "mock-v1"),
                prompt_template_version="revision_v1",
            )
            db.add(item_ver)
            db.flush()
            item.latest_version_id = item_ver.id
        created_assets.append(rev_asset)

        db.commit()
        for a in created_assets:
            db.refresh(a)
        
        # Run quality guardrails automatically
        from backend.app.guardrails.runner import run_unit_guardrails
        await run_unit_guardrails(db, unit.id, llm_provider)

        return created_assets

    except Exception as exc:
        db.rollback()
        raise exc
