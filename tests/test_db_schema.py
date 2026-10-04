"""Database schema creation and model validation tests."""

import pytest
from sqlalchemy import inspect
from backend.app.db.models import (
    SourceVersion,
    SourceChunk,
    Unit,
    Objective,
    Constraint,
    Asset,
    Item,
    ItemVersion,
    QualityFlag,
    GenerationRun,
    Decision,
)


def test_db_schema_tables_exist(db_engine):
    """Verify all 11 required tables exist in the database metadata."""
    inspector = inspect(db_engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "source_versions",
        "source_chunks",
        "units",
        "objectives",
        "constraints",
        "assets",
        "items",
        "item_versions",
        "quality_flags",
        "generation_runs",
        "decisions",
    }

    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_create_full_domain_entity_graph(db_session):
    """Verify full graph creation across source, unit, content, quality, and audit tables."""
    # 1. Source & Chunks
    source = SourceVersion(
        source_key="photosynthesis_v1",
        version_number=1,
        title="Photosynthesis Basics",
        raw_text="Plant leaves absorb sunlight...",
        content_hash="abc123hash",
        file_type="txt",
    )
    db_session.add(source)
    db_session.commit()

    chunk1 = SourceChunk(source_version_id=source.id, chunk_label="S1", position=1, text="Chlorophyll absorbs light.")
    chunk2 = SourceChunk(source_version_id=source.id, chunk_label="S2", position=2, text="Water is absorbed via roots.")
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # 2. Unit, Objective, Constraint
    unit = Unit(title="Grade 8 Biology: Photosynthesis", source_version_id=source.id, target_level="Grade 8", difficulty="medium")
    db_session.add(unit)
    db_session.commit()

    obj1 = Objective(unit_id=unit.id, code="O1", text="Describe inputs and outputs.", gap_status="supported")
    obj2 = Objective(unit_id=unit.id, code="O2", text="Explain chlorophyll role.", gap_status="supported")
    constraint = Constraint(unit_id=unit.id, vocabulary_level="standard", max_length_words=400, answer_reveal_policy="never_in_stem")
    db_session.add_all([obj1, obj2, constraint])
    db_session.commit()

    # 3. Asset & Item
    asset = Asset(unit_id=unit.id, asset_type="quiz")
    db_session.add(asset)
    db_session.commit()

    item = Item(asset_id=asset.id, position=1, item_type="mcq")
    db_session.add(item)
    db_session.commit()

    # 4. ItemVersion (with required objective_id and source_chunk_ids)
    run = GenerationRun(
        unit_id=unit.id,
        asset_type="quiz",
        status="success",
        attempts=1,
        model_id="mock-v1",
        prompt_template_version="quiz_v1",
    )
    db_session.add(run)
    db_session.commit()

    item_version = ItemVersion(
        item_id=item.id,
        version_number=1,
        content={"stem": "What is chlorophyll?", "options": [{"label": "A", "text": "Pigment"}]},
        status="Draft",
        objective_id=obj1.id,
        source_chunk_ids=["S1"],
        bloom_level="remember",
        source_version_id=source.id,
        model_id="mock-v1",
        prompt_template_version="quiz_v1",
        generation_run_id=run.id,
    )
    db_session.add(item_version)
    db_session.commit()

    # 5. QualityFlag & Decision
    flag = QualityFlag(
        item_version_id=item_version.id,
        flag_type="duplicate",
        severity="low",
        message="Potential duplicate stem",
        detected_by="deterministic",
    )
    decision = Decision(
        unit_id=unit.id,
        item_version_id=item_version.id,
        action="regenerate",
        actor="teacher",
        note="Regenerating Q1 for better clarity",
    )
    db_session.add_all([flag, decision])
    db_session.commit()

    # Query assertions
    retrieved_version = db_session.query(ItemVersion).filter_by(id=item_version.id).first()
    assert retrieved_version is not None
    assert retrieved_version.objective_id == obj1.id
    assert retrieved_version.source_chunk_ids == ["S1"]
    assert retrieved_version.status == "Draft"
