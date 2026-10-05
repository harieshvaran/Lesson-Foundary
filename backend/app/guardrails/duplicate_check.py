"""Guardrail 1: Check for duplicate or near-identical questions in a unit."""

import re
from backend.app.core.config import settings
from backend.app.guardrails.base import QualityFlagData


def _tokenize_stem(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", "", text.lower())
    words = [w for w in clean.split() if len(w) > 2]
    return set(words)


def check_duplicate_questions(
    item_versions: list[dict],
    threshold: float = settings.GUARDRAIL_DUP_JACCARD_THRESHOLD,
) -> list[QualityFlagData]:
    """Checks pairwise Jaccard similarity between question stems across items.
    
    item_versions element format: {"id": str, "item_type": str, "content": dict}
    """
    flags: list[QualityFlagData] = []
    question_items = [
        v for v in item_versions if v.get("content", {}).get("stem") or v.get("content", {}).get("prompt")
    ]

    for i in range(len(question_items)):
        for j in range(i + 1, len(question_items)):
            item_a = question_items[i]
            item_b = question_items[j]

            stem_a = item_a["content"].get("stem") or item_a["content"].get("prompt", "")
            stem_b = item_b["content"].get("stem") or item_b["content"].get("prompt", "")

            tokens_a = _tokenize_stem(stem_a)
            tokens_b = _tokenize_stem(stem_b)

            if not tokens_a or not tokens_b:
                continue

            intersection = tokens_a.intersection(tokens_b)
            union = tokens_a.union(tokens_b)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= threshold:
                flags.append(
                    QualityFlagData(
                        item_version_id=item_a["id"],
                        flag_type="duplicate_question",
                        severity="medium",
                        message=f"Question stem is near-identical to another item in the unit (Jaccard similarity: {jaccard:.2f}).",
                        suggested_fix="Reword the question stem to test the objective from a different angle.",
                        detected_by="deterministic",
                    )
                )
                flags.append(
                    QualityFlagData(
                        item_version_id=item_b["id"],
                        flag_type="duplicate_question",
                        severity="medium",
                        message=f"Question stem is near-identical to another item in the unit (Jaccard similarity: {jaccard:.2f}).",
                        suggested_fix="Reword the question stem to test the objective from a different angle.",
                        detected_by="deterministic",
                    )
                )

    return flags
