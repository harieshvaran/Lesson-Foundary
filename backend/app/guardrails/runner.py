"""Guardrail orchestrator runner for evaluating items and persisting QualityFlag records."""

from typing import Any
from sqlalchemy.orm import Session

from backend.app.db.models.unit import Unit
from backend.app.db.models.content import Asset, Item, ItemVersion
from backend.app.db.models.source import SourceChunk
from backend.app.db.models.quality import QualityFlag
from backend.app.guardrails.base import QualityFlagData
from backend.app.guardrails.duplicate_check import check_duplicate_questions
from backend.app.guardrails.leakage_check import check_answer_leakage
from backend.app.guardrails.malformed_key_check import check_malformed_answer_key
from backend.app.guardrails.unsupported_claim_check import check_unsupported_claim
from backend.app.guardrails.imbalance_check import check_objective_imbalance
from backend.app.guardrails.difficulty_check import check_difficulty_mismatch
from backend.app.guardrails.revision_concept_check import check_revision_new_concepts


async def run_unit_guardrails(
    db: Session,
    unit_id: str,
    llm_provider: Any | None = None,
) -> list[QualityFlag]:
    """Runs all 7 guardrails over all latest ItemVersions in a unit and persists QualityFlag records."""
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        return []

    assets = db.query(Asset).filter_by(unit_id=unit_id).all()
    chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).all()
    source_chunks_dict = {c.chunk_label: c.text for c in chunks}
    source_chunk_texts = [c.text for c in chunks]

    # Collect latest versions per item
    all_item_versions: list[dict] = []
    item_version_objs: dict[str, ItemVersion] = {}
    easy_items: list[dict] = []
    advanced_items: list[dict] = []
    revision_items: list[dict] = []
    prior_context_items: list[dict] = []

    for asset in assets:
        for item in asset.items:
            if item.versions:
                latest_ver = max(item.versions, key=lambda v: v.version_number)
                ver_dict = {
                    "id": latest_ver.id,
                    "item_id": item.id,
                    "item_type": item.item_type,
                    "asset_type": asset.asset_type,
                    "objective_id": latest_ver.objective_id,
                    "source_chunk_ids": latest_ver.source_chunk_ids,
                    "bloom_level": latest_ver.bloom_level,
                    "content": latest_ver.content,
                }
                all_item_versions.append(ver_dict)
                item_version_objs[latest_ver.id] = latest_ver

                if asset.asset_type == "practice_easy":
                    easy_items.append(ver_dict)
                elif asset.asset_type == "practice_advanced":
                    advanced_items.append(ver_dict)
                elif asset.asset_type == "revision":
                    revision_items.append(ver_dict)
                elif asset.asset_type in ("explanation", "example"):
                    prior_context_items.append(ver_dict)

    flag_data_list: list[QualityFlagData] = []

    # Guardrail 1: Duplicate questions
    flag_data_list.extend(check_duplicate_questions(all_item_versions))

    # Guardrail 5: Objective imbalance
    obj_codes = [o.code for o in unit.objectives]
    flag_data_list.extend(check_objective_imbalance(obj_codes, all_item_versions))

    # Guardrail 6: Difficulty mismatch
    flag_data_list.extend(check_difficulty_mismatch(easy_items, advanced_items))

    # Guardrail 7: Revision new concept
    flag_data_list.extend(check_revision_new_concepts(revision_items, prior_context_items, source_chunk_texts))

    # Per-item guardrails (2, 3, 4)
    for ver_dict in all_item_versions:
        ver_id = ver_dict["id"]
        itype = ver_dict["item_type"]
        content = ver_dict["content"]
        cited_chunks = ver_dict["source_chunk_ids"]

        # Guardrail 2: Answer leakage
        flag_data_list.extend(check_answer_leakage(ver_id, itype, content))

        # Guardrail 3: Malformed answer key
        flag_data_list.extend(check_malformed_answer_key(ver_id, itype, content))

        # Guardrail 4: Unsupported claim
        unsupported_flags = await check_unsupported_claim(
            ver_id, content, cited_chunks, source_chunks_dict, llm_provider
        )
        flag_data_list.extend(unsupported_flags)

    # Persist flags to database
    persisted_flags: list[QualityFlag] = []
    for f in flag_data_list:
        # Check if identical unresolved flag already exists
        existing = (
            db.query(QualityFlag)
            .filter_by(
                item_version_id=f.item_version_id,
                flag_type=f.flag_type,
                resolved=False,
            )
            .first()
        )
        if not existing:
            flag_row = QualityFlag(
                item_version_id=f.item_version_id,
                flag_type=f.flag_type,
                severity=f.severity,
                message=f.message,
                suggested_fix=f.suggested_fix,
                detected_by=f.detected_by,
                resolved=False,
            )
            db.add(flag_row)
            persisted_flags.append(flag_row)

    if persisted_flags:
        db.commit()
        for pf in persisted_flags:
            db.refresh(pf)

    return persisted_flags
