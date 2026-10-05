"""Service for alignment matrix computation, objective counts, and coverage imbalance detection."""

import math
from sqlalchemy.orm import Session
from backend.app.db.models.unit import Unit
from backend.app.db.models.content import ItemVersion, Asset
from backend.app.db.models.source import SourceChunk


def compute_unit_alignment_matrix(db: Session, unit_id: str) -> dict:
    """Compute objective x asset coverage matrix, objective totals, asset totals, and imbalance warning."""
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        raise ValueError(f"Unit '{unit_id}' not found.")

    objectives = unit.objectives
    assets = db.query(Asset).filter_by(unit_id=unit.id).all()

    obj_codes = [o.code for o in objectives]
    obj_id_to_code = {o.id: o.code for o in objectives}
    obj_id_to_code.update({o.code: o.code for o in objectives})

    asset_types = ["explanation", "example", "quiz", "practice_easy", "practice_advanced", "revision"]
    matrix = {code: {atype: 0 for atype in asset_types} for code in obj_codes}

    all_cited_chunks = set()

    for asset in assets:
        for item in asset.items:
            # Pick latest version
            if item.versions:
                latest_ver = max(item.versions, key=lambda v: v.version_number)
                code = obj_id_to_code.get(latest_ver.objective_id, "Unknown")
                if code in matrix:
                    matrix[code][asset.asset_type] = matrix[code].get(asset.asset_type, 0) + 1
                all_cited_chunks.update(latest_ver.source_chunk_ids)

    # Compute totals
    objective_totals = {code: sum(matrix[code].values()) for code in obj_codes}
    asset_totals = {atype: sum(matrix[code][atype] for code in obj_codes) for atype in asset_types}

    total_items = sum(objective_totals.values())

    # Imbalance Warning Logic:
    # Trigger warning if total_items > 0 and any objective has < 15% of total items or standard deviation > threshold
    imbalance_warning = False
    imbalance_reason = None

    if total_items > 0 and len(obj_codes) > 1:
        counts = list(objective_totals.values())
        mean_count = total_items / len(obj_codes)
        min_allowed = total_items * 0.15

        for code, count in objective_totals.items():
            if count < min_allowed:
                imbalance_warning = True
                imbalance_reason = f"Objective '{code}' has only {count}/{total_items} items (< 15% threshold)."

        variance = sum((c - mean_count) ** 2 for c in counts) / len(counts)
        std_dev = math.sqrt(variance)
        if std_dev > (mean_count * 0.5):
            imbalance_warning = True
            if not imbalance_reason:
                imbalance_reason = f"High item count variation across objectives (std dev={std_dev:.2f})."

    # Find uncited chunks
    all_chunks = db.query(SourceChunk).filter_by(source_version_id=unit.source_version_id).all()
    uncited_chunks = [c.chunk_label for c in all_chunks if c.chunk_label not in all_cited_chunks]

    return {
        "unit_id": unit.id,
        "total_items": total_items,
        "objectives": obj_codes,
        "asset_types": asset_types,
        "matrix": matrix,
        "objective_totals": objective_totals,
        "asset_totals": asset_totals,
        "imbalance_warning": imbalance_warning,
        "imbalance_reason": imbalance_reason,
        "uncited_chunks": uncited_chunks,
    }
