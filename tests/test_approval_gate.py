"""Pytest test suite for Approval Gate high-severity flag blocking and logged override."""

import pytest
from backend.app.services.source_service import create_source_version
from backend.app.services.unit_service import create_unit_with_objectives
from backend.app.services.approval_service import approve_item_version
from backend.app.core.exceptions import ApprovalBlockedException
from backend.app.db.models.quality import QualityFlag
from backend.app.db.models.audit import Decision
from backend.app.db.models.content import Item, ItemVersion, Asset


def test_approval_blocked_on_high_severity_flag(db_session, sample_source_bytes):
    src = create_source_version(db_session, sample_source_bytes, "normal.txt", "Test Title", "src_gate_1")
    unit = create_unit_with_objectives(
        db_session,
        title="Gate Unit",
        source_version_id=src.id,
        objectives_data=[{"code": "O1", "text": "Inputs"}, {"code": "O2", "text": "Outputs"}],
    )

    asset = Asset(unit_id=unit.id, asset_type="quiz")
    db_session.add(asset)
    db_session.flush()

    item = Item(asset_id=asset.id, position=1, item_type="mcq")
    db_session.add(item)
    db_session.flush()

    ver = ItemVersion(
        item_id=item.id,
        version_number=1,
        content={"stem": "Leaked answer stem", "options": [], "correct_label": "A"},
        status="Draft",
        objective_id=unit.objectives[0].id,
        source_chunk_ids=["S1"],
        source_version_id=src.id,
        model_id="mock",
        prompt_template_version="v1",
    )
    db_session.add(ver)
    db_session.flush()
    item.latest_version_id = ver.id

    # Add a HIGH severity unresolved quality flag
    flag = QualityFlag(
        item_version_id=ver.id,
        flag_type="answer_leakage",
        severity="high",
        message="Answer leakage detected in stem",
        resolved=False,
    )
    db_session.add(flag)
    db_session.commit()

    # Attempt approval without override -> Should raise ApprovalBlockedException
    with pytest.raises(ApprovalBlockedException) as exc_info:
        approve_item_version(db_session, ver.id, override=False)

    assert "unresolved high-severity quality flags" in str(exc_info.value)
    assert ver.status == "Draft"  # Remains Draft!

    # Now approve WITH override=True and override_note
    approved_ver = approve_item_version(
        db_session,
        ver.id,
        override=True,
        override_note="Teacher confirmed key phrase leakage is acceptable in context",
    )

    assert approved_ver.status == "Approved"
    assert item.current_approved_version_id == approved_ver.id

    # Verify Decision row logged action="flag_override"
    decision = db_session.query(Decision).filter_by(item_version_id=ver.id).first()
    assert decision is not None
    assert decision.action == "flag_override"
    assert "Teacher confirmed" in decision.note
