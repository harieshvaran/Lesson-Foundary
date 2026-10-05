"""Pytest test suite for all 7 content quality guardrails (Positive and Negative detection)."""

import pytest
from backend.app.guardrails.duplicate_check import check_duplicate_questions
from backend.app.guardrails.leakage_check import check_answer_leakage
from backend.app.guardrails.malformed_key_check import check_malformed_answer_key
from backend.app.guardrails.unsupported_claim_check import check_unsupported_claim
from backend.app.guardrails.imbalance_check import check_objective_imbalance
from backend.app.guardrails.difficulty_check import check_difficulty_mismatch
from backend.app.guardrails.revision_concept_check import check_revision_new_concepts


# --- Guardrail 1: Duplicate Questions ---
def test_guardrail_duplicate_questions_positive():
    items = [
        {"id": "v1", "item_type": "mcq", "content": {"stem": "What is the primary role of chlorophyll in photosynthesis?"}},
        {"id": "v2", "item_type": "mcq", "content": {"stem": "What is the main role of chlorophyll in photosynthesis?"}},
    ]
    flags = check_duplicate_questions(items, threshold=0.70)
    assert len(flags) == 2
    assert flags[0].flag_type == "duplicate_question"
    assert flags[0].severity == "medium"


def test_guardrail_duplicate_questions_negative():
    items = [
        {"id": "v1", "item_type": "mcq", "content": {"stem": "Where does the light reaction take place in plant cells?"}},
        {"id": "v2", "item_type": "mcq", "content": {"stem": "What is the chemical formula for glucose synthesis?"}},
    ]
    flags = check_duplicate_questions(items, threshold=0.70)
    assert len(flags) == 0


# --- Guardrail 2: Answer Leakage ---
def test_guardrail_answer_leakage_positive():
    content = {
        "stem": "Chlorophyll absorbs light energy to produce glucose in plants.",
        "options": [
            {"label": "A", "text": "Mitochondria"},
            {"label": "B", "text": "Chlorophyll and light energy"},
            {"label": "C", "text": "Cell wall"},
            {"label": "D", "text": "Nucleus"},
        ],
        "correct_label": "B",
    }
    flags = check_answer_leakage("v1", "mcq", content, min_words=3)
    assert len(flags) >= 1
    assert flags[0].flag_type == "answer_leakage"
    assert flags[0].severity == "high"


def test_guardrail_answer_leakage_negative():
    content = {
        "stem": "Which organelle absorbs light during photosynthesis?",
        "options": [
            {"label": "A", "text": "Mitochondria"},
            {"label": "B", "text": "Chloroplast"},
            {"label": "C", "text": "Ribosome"},
            {"label": "D", "text": "Vacuole"},
        ],
        "correct_label": "B",
    }
    flags = check_answer_leakage("v1", "mcq", content, min_words=3)
    assert len(flags) == 0


# --- Guardrail 3: Malformed Answer Key ---
def test_guardrail_malformed_key_missing_label():
    content = {
        "stem": "What is produced?",
        "options": [
            {"label": "A", "text": "Oxygen"},
            {"label": "B", "text": "Water"},
        ],
        "correct_label": "D",  # Missing
        "rationale": "Option D is correct.",
    }
    flags = check_malformed_answer_key("v1", "mcq", content)
    assert any(f.flag_type == "malformed_answer_key" for f in flags)


def test_guardrail_malformed_key_rationale_contradiction():
    content = {
        "stem": "What is produced?",
        "options": [
            {"label": "A", "text": "Oxygen"},
            {"label": "B", "text": "Water"},
            {"label": "C", "text": "Glucose"},
            {"label": "D", "text": "Nitrogen"},
        ],
        "correct_label": "C",
        "rationale": "Option A is correct because plants release oxygen.",  # Contradicts C
    }
    flags = check_malformed_answer_key("v1", "mcq", content)
    assert any("contradicting key" in f.message for f in flags)


def test_guardrail_malformed_key_negative():
    content = {
        "stem": "What is produced?",
        "options": [
            {"label": "A", "text": "Oxygen"},
            {"label": "B", "text": "Water"},
            {"label": "C", "text": "Glucose"},
            {"label": "D", "text": "Nitrogen"},
        ],
        "correct_label": "C",
        "rationale": "Option C is correct because glucose is the sugar created.",
    }
    flags = check_malformed_answer_key("v1", "mcq", content)
    assert len(flags) == 0


# --- Guardrail 4: Unsupported Claim ---
@pytest.mark.asyncio
async def test_guardrail_unsupported_claim_missing_citation():
    flags = await check_unsupported_claim(
        item_version_id="v1",
        content={"stem": "Glucose is synthesized in chloroplasts."},
        cited_chunk_ids=[],  # Missing
        source_chunks_dict={"S1": "Chloroplasts contain chlorophyll."},
    )
    assert len(flags) == 1
    assert flags[0].flag_type == "unsupported_claim"
    assert flags[0].severity == "high"


@pytest.mark.asyncio
async def test_guardrail_unsupported_claim_low_overlap():
    flags = await check_unsupported_claim(
        item_version_id="v1",
        content={"stem": "Mitochondria produce ATP during solar radiation absorption."},
        cited_chunk_ids=["S1"],
        source_chunks_dict={"S1": "Chloroplasts contain chlorophyll pigments that absorb light."},
    )
    assert len(flags) == 1
    assert flags[0].flag_type == "unsupported_claim"
    assert flags[0].severity == "high"


@pytest.mark.asyncio
async def test_guardrail_unsupported_claim_negative():
    flags = await check_unsupported_claim(
        item_version_id="v1",
        content={"stem": "Chloroplasts contain chlorophyll pigments that absorb light."},
        cited_chunk_ids=["S1"],
        source_chunks_dict={"S1": "Chloroplasts contain chlorophyll pigments that absorb light energy."},
    )
    assert len(flags) == 0


# --- Guardrail 5: Objective Imbalance ---
def test_guardrail_objective_imbalance_positive():
    items = [
        {"id": f"v{i}", "objective_id": "O1"} for i in range(9)
    ] + [{"id": "v9", "objective_id": "O2"}]  # 9 vs 1

    flags = check_objective_imbalance(["O1", "O2"], items, min_ratio=0.15)
    assert len(flags) >= 1
    assert flags[0].flag_type == "objective_imbalance"


def test_guardrail_objective_imbalance_negative():
    items = [
        {"id": f"v{i}", "objective_id": "O1"} for i in range(5)
    ] + [{"id": f"v{i+5}", "objective_id": "O2"} for i in range(5)]

    flags = check_objective_imbalance(["O1", "O2"], items, min_ratio=0.15)
    assert len(flags) == 0


# --- Guardrail 6: Difficulty Mismatch ---
def test_guardrail_difficulty_mismatch_positive():
    easy_items = [{"id": "e1", "bloom_level": "evaluate"}]  # Rank 5 > max 2
    adv_items = [{"id": "a1", "bloom_level": "remember"}]   # Rank 1 < min 3

    flags = check_difficulty_mismatch(easy_items, adv_items)
    assert len(flags) >= 2
    assert all(f.flag_type == "difficulty_mismatch" for f in flags)


def test_guardrail_difficulty_mismatch_negative():
    easy_items = [{"id": "e1", "bloom_level": "remember"}, {"id": "e2", "bloom_level": "understand"}]
    adv_items = [{"id": "a1", "bloom_level": "apply"}, {"id": "a2", "bloom_level": "analyze"}]

    flags = check_difficulty_mismatch(easy_items, adv_items)
    assert len(flags) == 0


# --- Guardrail 7: Revision New Concept ---
def test_guardrail_revision_new_concept_positive():
    revision_items = [{"id": "r1", "content": {"point": "Chemiosmosis photophosphorylation occurs during light reactions."}}]
    prior_items = [{"id": "p1", "content": {"body": "Chlorophyll absorbs light to turn carbon dioxide and water into glucose."}}]
    source_texts = ["Plants use chlorophyll for photosynthesis."]

    flags = check_revision_new_concepts(revision_items, prior_items, source_texts)
    assert len(flags) == 1
    assert flags[0].flag_type == "revision_new_concept"


def test_guardrail_revision_new_concept_negative():
    revision_items = [{"id": "r1", "content": {"point": "Chlorophyll absorbs light to turn carbon dioxide into glucose."}}]
    prior_items = [{"id": "p1", "content": {"body": "Chlorophyll absorbs light to turn carbon dioxide into glucose."}}]
    source_texts = ["Plants use chlorophyll for photosynthesis."]

    flags = check_revision_new_concepts(revision_items, prior_items, source_texts)
    assert len(flags) == 0
