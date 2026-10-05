"""Guardrail 3: Check for malformed answer key or option contradictions."""

import re
from backend.app.guardrails.base import QualityFlagData


def check_malformed_answer_key(
    item_version_id: str,
    item_type: str,
    content: dict,
) -> list[QualityFlagData]:
    """Checks if MCQ correct_label is missing from options, options have duplicates, or rationale contradicts key."""
    flags: list[QualityFlagData] = []

    if item_type != "mcq":
        return flags

    options = content.get("options", [])
    correct_label = content.get("correct_label")
    rationale = content.get("rationale", "")

    labels = [opt.get("label") for opt in options]
    texts = [opt.get("text", "").strip().lower() for opt in options if opt.get("text")]

    # 1. Label missing
    if correct_label not in labels:
        flags.append(
            QualityFlagData(
                item_version_id=item_version_id,
                flag_type="malformed_answer_key",
                severity="high",
                message=f"correct_label '{correct_label}' is not present in the options list {labels}.",
                suggested_fix="Ensure correct_label matches one of the option labels A, B, C, or D.",
                detected_by="deterministic",
            )
        )

    # 2. Duplicate option texts
    if len(texts) != len(set(texts)):
        flags.append(
            QualityFlagData(
                item_version_id=item_version_id,
                flag_type="malformed_answer_key",
                severity="high",
                message="Multiple options contain identical answer text.",
                suggested_fix="Ensure all four option choices are distinct.",
                detected_by="deterministic",
            )
        )

    # 3. Rationale contradiction (e.g. "Option A is correct" when correct_label == "C")
    if rationale and correct_label:
        match = re.search(r"option\s+([A-D])\s+is\s+(correct|right)", rationale, re.IGNORECASE)
        if match:
            rationale_label = match.group(1).upper()
            if rationale_label != correct_label:
                flags.append(
                    QualityFlagData(
                        item_version_id=item_version_id,
                        flag_type="malformed_answer_key",
                        severity="high",
                        message=f"Rationale states Option {rationale_label} is correct, contradicting key '{correct_label}'.",
                        suggested_fix=f"Align rationale text with correct_label '{correct_label}'.",
                        detected_by="deterministic",
                    )
                )

    return flags
