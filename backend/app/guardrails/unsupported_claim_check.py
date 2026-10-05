"""Guardrail 4: Check for unsupported claims against cited source chunks (Deterministic + LLM Backup)."""

import re
from typing import Any
from backend.app.core.config import settings
from backend.app.guardrails.base import QualityFlagData
from backend.app.generation.prompts.templates import load_prompt_template, render_template


def _tokenize(text: str) -> set[str]:
    clean = re.sub(r"[^\w\s]", "", text.lower())
    words = [w for w in clean.split() if len(w) > 2]
    return set(words)


async def check_unsupported_claim(
    item_version_id: str,
    content: dict,
    cited_chunk_ids: list[str],
    source_chunks_dict: dict[str, str],  # {"S1": "chunk text", ...}
    llm_provider: Any | None = None,
) -> list[QualityFlagData]:
    """Validates that cited chunk IDs exist and content is supported by cited source text."""
    flags: list[QualityFlagData] = []

    # 1. Missing or empty citations
    if not cited_chunk_ids:
        flags.append(
            QualityFlagData(
                item_version_id=item_version_id,
                flag_type="unsupported_claim",
                severity="high",
                message="Item contains no source chunk citations.",
                suggested_fix="Cite at least one source chunk (S1, S2, ...) that supports this item.",
                detected_by="deterministic",
            )
        )
        return flags

    # 2. Invalid chunk IDs cited
    invalid_ids = [cid for cid in cited_chunk_ids if cid not in source_chunks_dict]
    if invalid_ids:
        flags.append(
            QualityFlagData(
                item_version_id=item_version_id,
                flag_type="unsupported_claim",
                severity="high",
                message=f"Item cites chunk IDs {invalid_ids} which do not exist in the source version.",
                suggested_fix="Update citations to valid source chunk labels.",
                detected_by="deterministic",
            )
        )
        return flags

    # Combine item text
    item_str = ""
    for k in ["heading", "body", "stem", "prompt", "model_answer", "point", "instruction", "working"]:
        if k in content and isinstance(content[k], str):
            item_str += " " + content[k]

    item_tokens = _tokenize(item_str)
    if not item_tokens:
        return flags

    # Combine cited chunk texts
    chunk_str = " ".join(source_chunks_dict[cid] for cid in cited_chunk_ids if cid in source_chunks_dict)
    chunk_tokens = _tokenize(chunk_str)

    if not chunk_tokens:
        overlap = 0.0
    else:
        intersection = item_tokens.intersection(chunk_tokens)
        overlap = len(intersection) / len(item_tokens)

    # 3. Lexical overlap check
    if overlap < settings.GUARDRAIL_CLAIM_OVERLAP_MIN_THRESHOLD:
        # LLM Entailment Backup if provider available
        if llm_provider and settings.GUARDRAIL_ENABLE_LLM_ENTAILMENT:
            try:
                entail_template = load_prompt_template("claim_entailment_v1.txt")
                rendered_prompt = render_template(
                    entail_template,
                    {
                        "claim": item_str.strip(),
                        "chunks": chunk_str.strip(),
                    },
                )
                system_prompt = load_prompt_template("system_prompt_v1.txt")

                from pydantic import BaseModel

                class EntailmentOutput(BaseModel):
                    supported: bool
                    reason: str

                result: EntailmentOutput = await llm_provider.generate_structured(
                    prompt=rendered_prompt,
                    schema=EntailmentOutput,
                    system_prompt=system_prompt,
                )

                if not result.supported:
                    flags.append(
                        QualityFlagData(
                            item_version_id=item_version_id,
                            flag_type="unsupported_claim",
                            severity="high",
                            message=f"LLM entailment check found claims unsupported by cited chunks ({result.reason}).",
                            suggested_fix="Ensure all claims in the item are explicitly supported by cited source chunks.",
                            detected_by="llm",
                        )
                    )
            except Exception:
                # Fallback to deterministic flag if LLM call fails
                flags.append(
                    QualityFlagData(
                        item_version_id=item_version_id,
                        flag_type="unsupported_claim",
                        severity="high",
                        message=f"Low lexical token overlap ({overlap:.2f}) with cited source chunks.",
                        suggested_fix="Ensure item content uses facts supported by cited source chunks.",
                        detected_by="deterministic",
                    )
                )
        else:
            flags.append(
                QualityFlagData(
                    item_version_id=item_version_id,
                    flag_type="unsupported_claim",
                    severity="high",
                    message=f"Low lexical token overlap ({overlap:.2f}) with cited source chunks.",
                    suggested_fix="Ensure item content uses facts supported by cited source chunks.",
                    detected_by="deterministic",
                )
            )

    return flags
