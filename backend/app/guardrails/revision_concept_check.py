"""Guardrail 7: Check if revision sheet introduces new concepts absent from explanation/example."""

import re
from backend.app.guardrails.base import QualityFlagData


def _extract_words(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", "", text.lower())
    return {w for w in clean.split() if len(w) > 3}


def check_revision_new_concepts(
    revision_items: list[dict],       # [{"id": str, "content": {"point": str}}, ...]
    prior_context_items: list[dict], # explanation and example items
    source_chunk_texts: list[str],
) -> list[QualityFlagData]:
    """Checks that revision point concepts were introduced in prior explanation/example."""
    flags: list[QualityFlagData] = []

    # Gather known words
    known_words = set()
    for item in prior_context_items:
        c = item.get("content", {})
        for text_val in c.values():
            if isinstance(text_val, str):
                known_words.update(_extract_words(text_val))

    for s_text in source_chunk_texts:
        known_words.update(_extract_words(s_text))

    for rev in revision_items:
        point_text = rev.get("content", {}).get("point", "")
        if not point_text:
            continue

        rev_words = _extract_words(point_text)
        new_words = rev_words - known_words

        # If more than 2 significant new words appear that weren't in prior context/source
        if len(new_words) >= 2:
            new_list = ", ".join(f"'{w}'" for w in list(new_words)[:3])
            flags.append(
                QualityFlagData(
                    item_version_id=rev["id"],
                    flag_type="revision_new_concept",
                    severity="medium",
                    message=f"Revision point introduces new terms ({new_list}) not present in the explanation or example.",
                    suggested_fix="Ensure all revision points restate concepts already introduced in the explanation.",
                    detected_by="deterministic",
                )
            )

    return flags
