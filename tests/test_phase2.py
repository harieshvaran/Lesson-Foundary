"""Phase 2 invariant tests: approved immutability, regeneration isolation (byte-identical hash comparison), full pack pipeline, and alignment matrix."""

import hashlib
import json
import pytest

from backend.app.services.source_service import create_source_version
from backend.app.services.unit_service import create_unit_with_objectives
from backend.app.services.generation_service import generate_full_pack, generate_quiz_asset
from backend.app.services.approval_service import approve_item_version, regenerate_single_item
from backend.app.services.alignment_service import compute_unit_alignment_matrix
from backend.app.db.models.content import Item, ItemVersion
from backend.app.core.exceptions import ImmutableApprovedVersionException
from tests.test_double_provider import TestDoubleLLMProvider


@pytest.mark.asyncio
async def test_approved_item_immutability(db_session):
    """Verify Rule 3.1: Approved item_versions cannot be updated or deleted."""
    source_ver = create_source_version(
        db=db_session,
        file_bytes=b"Photosynthesis converts carbon dioxide and water into glucose and oxygen.",
        filename="normal.txt",
        title="Photosynthesis",
    )
    unit = create_unit_with_objectives(
        db=db_session,
        title="Immutability Unit",
        source_version_id=source_ver.id,
        objectives_data=[
            {"code": "O1", "text": "Inputs and outputs"},
            {"code": "O2", "text": "Chlorophyll role"},
        ],
    )
    for o in unit.objectives:
        o.gap_status = "supported"
    db_session.commit()

    provider = TestDoubleLLMProvider()
    asset = await generate_quiz_asset(db_session, unit.id, provider)
    item = asset.items[0]
    draft_ver = item.versions[0]

    # Approve item version
    approved_ver = approve_item_version(db_session, draft_ver.id)
    assert approved_ver.status == "Approved"

    # Attempting to modify content of Approved version must raise ImmutableApprovedVersionException
    approved_ver.content = {"stem": "Hacked stem content"}
    with pytest.raises(ImmutableApprovedVersionException):
        db_session.commit()

    db_session.rollback()

    # Attempting to delete Approved version must raise ImmutableApprovedVersionException
    db_session.delete(approved_ver)
    with pytest.raises(ImmutableApprovedVersionException):
        db_session.commit()


@pytest.mark.asyncio
async def test_selective_regeneration_byte_isolation(db_session):
    """Verify Rule 3.3 & TC5: Regenerating Q4 leaves Q1, Q2, Q3 byte-identical."""
    source_ver = create_source_version(
        db=db_session,
        file_bytes=b"Photosynthesis converts carbon dioxide and water into glucose and oxygen using chlorophyll.",
        filename="normal.txt",
        title="Photosynthesis",
    )
    unit = create_unit_with_objectives(
        db=db_session,
        title="Regen Unit",
        source_version_id=source_ver.id,
        objectives_data=[
            {"code": "O1", "text": "Inputs and outputs"},
            {"code": "O2", "text": "Chlorophyll role"},
        ],
    )
    for o in unit.objectives:
        o.gap_status = "supported"
    db_session.commit()

    provider = TestDoubleLLMProvider()
    asset = await generate_quiz_asset(db_session, unit.id, provider, num_questions=4)
    items = asset.items
    assert len(items) == 4

    # Approve Q1, Q2, Q3
    for it in items[:3]:
        approve_item_version(db_session, it.versions[0].id)

    # Compute SHA-256 hashes of content for Q1, Q2, Q3 before regeneration
    def compute_item_hash(item_obj: Item) -> str:
        latest = item_obj.versions[-1]
        data_str = json.dumps(latest.content, sort_keys=True)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    hashes_before = [compute_item_hash(it) for it in items[:3]]

    # Regenerate Q4
    target_q4 = items[3]
    q4_version_count_before = len(target_q4.versions)
    new_q4_ver = await regenerate_single_item(db_session, target_q4.id, provider, teacher_feedback="Make Q4 harder")

    db_session.refresh(asset)

    # 1. Q4 gets new version in Draft
    assert len(target_q4.versions) == q4_version_count_before + 1
    assert new_q4_ver.version_number == 2
    assert new_q4_ver.status == "Draft"

    # 2. Q1, Q2, Q3 remain byte-identical before and after
    hashes_after = [compute_item_hash(it) for it in items[:3]]
    assert hashes_before == hashes_after, "Regeneration altered un-targeted items!"


@pytest.mark.asyncio
async def test_full_pack_pipeline_generation(db_session):
    """Verify full 5-artifact pipeline generation."""
    source_ver = create_source_version(
        db=db_session,
        file_bytes=b"Photosynthesis converts carbon dioxide and water into glucose and oxygen using light and chlorophyll in chloroplasts.",
        filename="full_source.txt",
        title="Full Source",
    )
    unit = create_unit_with_objectives(
        db=db_session,
        title="Full Pack Unit",
        source_version_id=source_ver.id,
        objectives_data=[
            {"code": "O1", "text": "Describe inputs and outputs"},
            {"code": "O2", "text": "Explain chlorophyll function"},
        ],
    )
    for o in unit.objectives:
        o.gap_status = "supported"
    db_session.commit()

    provider = TestDoubleLLMProvider()
    assets = await generate_full_pack(db_session, unit.id, provider)

    asset_types = [a.asset_type for a in assets]
    assert asset_types == ["explanation", "example", "quiz", "practice_easy", "practice_advanced", "revision"]

    # Verify alignment matrix
    matrix_res = compute_unit_alignment_matrix(db_session, unit.id)
    assert matrix_res["total_items"] > 0
    assert "O1" in matrix_res["matrix"]
    assert "O2" in matrix_res["matrix"]
