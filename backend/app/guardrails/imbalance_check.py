"""Guardrail 5: Check for objective coverage imbalance across items in a unit."""

import math
from backend.app.core.config import settings
from backend.app.guardrails.base import QualityFlagData


def check_objective_imbalance(
    objective_codes: list[str],
    item_versions: list[dict],
    min_ratio: float = settings.GUARDRAIL_MIN_OBJ_COVERAGE_RATIO,
) -> list[QualityFlagData]:
    """Checks if objective item counts deviate beyond acceptable threshold."""
    flags: list[QualityFlagData] = []
    if not objective_codes or not item_versions:
        return flags

    counts = {code: 0 for code in objective_codes}
    for v in item_versions:
        obj_id = v.get("objective_id")
        if obj_id in counts:
            counts[obj_id] += 1

    total_items = len(item_versions)
    if total_items == 0 or len(objective_codes) <= 1:
        return flags

    min_allowed = total_items * min_ratio
    mean_count = total_items / len(objective_codes)
    variance = sum((c - mean_count) ** 2 for c in counts.values()) / len(objective_codes)
    std_dev = math.sqrt(variance)

    imbalanced_objs = [code for code, count in counts.items() if count < min_allowed]

    if imbalanced_objs or (std_dev > (mean_count * settings.GUARDRAIL_OBJ_IMBALANCE_STD_DEV_MULTIPLIER)):
        for v in item_versions:
            if v.get("objective_id") in imbalanced_objs:
                flags.append(
                    QualityFlagData(
                        item_version_id=v["id"],
                        flag_type="objective_imbalance",
                        severity="medium",
                        message=f"Objective '{v.get('objective_id')}' is under-represented ({counts.get(v.get('objective_id'), 0)}/{total_items} items).",
                        suggested_fix="Generate additional items for this objective to ensure balanced coverage.",
                        detected_by="deterministic",
                    )
                )

    return flags
