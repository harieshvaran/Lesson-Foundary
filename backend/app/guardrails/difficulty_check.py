"""Guardrail 6: Check for difficulty mismatch between easy and advanced items."""

from backend.app.core.config import settings
from backend.app.guardrails.base import QualityFlagData

BLOOM_RANKS = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}


def check_difficulty_mismatch(
    easy_items: list[dict],      # [{"id": str, "bloom_level": str}, ...]
    advanced_items: list[dict],  # [{"id": str, "bloom_level": str}, ...]
) -> list[QualityFlagData]:
    """Checks that easy and advanced practice items conform to allowed Bloom bands."""
    flags: list[QualityFlagData] = []

    # Check easy items
    easy_ranks = []
    for it in easy_items:
        bloom = (it.get("bloom_level") or "understand").lower()
        rank = BLOOM_RANKS.get(bloom, 2)
        easy_ranks.append(rank)

        if rank > settings.GUARDRAIL_EASY_BLOOM_MAX_RANK:
            flags.append(
                QualityFlagData(
                    item_version_id=it["id"],
                    flag_type="difficulty_mismatch",
                    severity="medium",
                    message=f"Easy item assigned Bloom level '{bloom}' (rank {rank} > max allowed {settings.GUARDRAIL_EASY_BLOOM_MAX_RANK}).",
                    suggested_fix="Adjust Bloom level to Remember or Understand for easy practice.",
                    detected_by="deterministic",
                )
            )

    # Check advanced items
    adv_ranks = []
    for it in advanced_items:
        bloom = (it.get("bloom_level") or "apply").lower()
        rank = BLOOM_RANKS.get(bloom, 3)
        adv_ranks.append(rank)

        if rank < settings.GUARDRAIL_ADVANCED_BLOOM_MIN_RANK:
            flags.append(
                QualityFlagData(
                    item_version_id=it["id"],
                    flag_type="difficulty_mismatch",
                    severity="medium",
                    message=f"Advanced item assigned Bloom level '{bloom}' (rank {rank} < min required {settings.GUARDRAIL_ADVANCED_BLOOM_MIN_RANK}).",
                    suggested_fix="Adjust Bloom level to Apply, Analyze, or Evaluate for advanced practice.",
                    detected_by="deterministic",
                )
            )

    # Unit-wide mean check
    if easy_ranks and adv_ranks:
        mean_easy = sum(easy_ranks) / len(easy_ranks)
        mean_adv = sum(adv_ranks) / len(adv_ranks)

        if mean_adv <= mean_easy:
            for it in advanced_items:
                flags.append(
                    QualityFlagData(
                        item_version_id=it["id"],
                        flag_type="difficulty_mismatch",
                        severity="medium",
                        message=f"Advanced cognitive demand (mean Bloom {mean_adv:.2f}) does not exceed easy (mean Bloom {mean_easy:.2f}).",
                        suggested_fix="Increase structural complexity and Bloom level for advanced items.",
                        detected_by="deterministic",
                    )
                )

    return flags
