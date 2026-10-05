"""Guardrail 2: Check for answer leakage in question stem."""

import re
from backend.app.core.config import settings
from backend.app.guardrails.base import QualityFlagData


def check_answer_leakage(
    item_version_id: str,
    item_type: str,
    content: dict,
    min_words: int = settings.GUARDRAIL_ANSWER_LEAKAGE_MIN_WORDS,
) -> list[QualityFlagData]:
    """Checks if the correct answer or marking points leak into the stem/prompt."""
    flags: list[QualityFlagData] = []

    if item_type == "mcq":
        stem = content.get("stem", "").lower()
        options = content.get("options", [])
        correct_label = content.get("correct_label")

        correct_option_text = ""
        for opt in options:
            if opt.get("label") == correct_label:
                correct_option_text = opt.get("text", "")
                break

        if correct_option_text and stem:
            clean_correct = re.sub(r"[^\w\s]", "", correct_option_text.lower()).strip()
            words = clean_correct.split()
            content_words = [w for w in words if len(w) >= 4]

            # 1. Full string match
            if clean_correct in stem and len(words) >= 1:
                flags.append(
                    QualityFlagData(
                        item_version_id=item_version_id,
                        flag_type="answer_leakage",
                        severity="high",
                        message=f"The correct option text '{correct_option_text}' appears inside the question stem.",
                        suggested_fix="Remove any hint or restatement of the correct option from the question stem.",
                        detected_by="deterministic",
                    )
                )
            # 2. Key n-gram match
            elif len(words) >= min_words:
                found_ngram = False
                for start_idx in range(len(words) - min_words + 1):
                    sub_phrase = " ".join(words[start_idx : start_idx + min_words])
                    if sub_phrase in stem:
                        flags.append(
                            QualityFlagData(
                                item_version_id=item_version_id,
                                flag_type="answer_leakage",
                                severity="high",
                                message=f"The key phrase '{sub_phrase}' from the correct option appears in the stem.",
                                suggested_fix="Rephrase the stem to avoid giving away key terms of the correct answer.",
                                detected_by="deterministic",
                            )
                        )
                        found_ngram = True
                        break

                if not found_ngram and len(content_words) >= 2:
                    stem_words = set(re.sub(r"[^\w\s]", "", stem.lower()).split())
                    matching = [w for w in content_words if w in stem_words]
                    if len(matching) >= 2:
                        flags.append(
                            QualityFlagData(
                                item_version_id=item_version_id,
                                flag_type="answer_leakage",
                                severity="high",
                                message=f"Multiple key terms ({', '.join(matching)}) from the correct option appear in the stem.",
                                suggested_fix="Rephrase the stem to avoid revealing key terms of the correct answer.",
                                detected_by="deterministic",
                            )
                        )

    elif item_type == "short_answer":
        prompt = content.get("prompt", "").lower()
        model_answer = content.get("model_answer", "").lower()
        marking_points = content.get("marking_points", [])

        if model_answer and prompt:
            clean_ans = re.sub(r"[^\w\s]", "", model_answer).strip()
            ans_words = clean_ans.split()
            if len(ans_words) >= min_words:
                for start_idx in range(len(ans_words) - min_words + 1):
                    sub_phrase = " ".join(ans_words[start_idx : start_idx + min_words])
                    if sub_phrase in prompt:
                        flags.append(
                            QualityFlagData(
                                item_version_id=item_version_id,
                                flag_type="answer_leakage",
                                severity="high",
                                message=f"Key answer phrase '{sub_phrase}' appears in the question prompt.",
                                suggested_fix="Remove model answer terminology from the question prompt.",
                                detected_by="deterministic",
                            )
                        )
                        break

    return flags
