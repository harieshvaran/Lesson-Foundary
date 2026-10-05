"""Pytest test suite for Student Mode API endpoints and HTML/PDF export isolation."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.source_service import create_source_version
from backend.app.services.unit_service import create_unit_with_objectives
from backend.app.services.generation_service import generate_quiz_asset
from backend.app.services.approval_service import approve_item_version

client = TestClient(app)


def test_student_unit_query_returns_approved_only(client, db_session, sample_source_bytes):
    # 1. Setup source and unit
    src = create_source_version(db_session, sample_source_bytes, "normal.txt", "Test Title", "src_stud_1")
    unit = create_unit_with_objectives(
        db_session,
        title="Student Test Unit",
        source_version_id=src.id,
        objectives_data=[
            {"code": "O1", "text": "Inputs and outputs"},
            {"code": "O2", "text": "Role of chlorophyll"},
        ],
    )
    for o in unit.objectives:
        o.gap_status = "supported"
    db_session.commit()

    # 2. Generate quiz (all 4 questions in Draft state initially)
    from tests.test_double_provider import TestDoubleLLMProvider
    provider = TestDoubleLLMProvider()

    import asyncio
    quiz_asset = asyncio.run(generate_quiz_asset(db_session, unit.id, provider, num_questions=4))
    items = quiz_asset.items

    # 3. Query student endpoint before any approval
    response = client.get(f"/api/v1/student/units/{unit.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 0  # No approved items yet!

    # 4. Approve Q1 and Q2 only
    q1_ver = items[0].versions[0]
    q2_ver = items[1].versions[0]
    approve_item_version(db_session, q1_ver.id)
    approve_item_version(db_session, q2_ver.id)

    # 5. Query student endpoint again
    response = client.get(f"/api/v1/student/units/{unit.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["assets"]) == 1
    assert len(data["assets"][0]["items"]) == 2  # Exactly 2 approved items!

    # 6. Test direct ID query for Approved item (Q1) -> 200 OK
    resp_q1 = client.get(f"/api/v1/student/items/{items[0].id}")
    assert resp_q1.status_code == 200
    assert resp_q1.json()["item_id"] == items[0].id

    # 7. Test direct ID query for Draft item (Q3) -> 404 Not Found (Rule 4.1)
    resp_q3 = client.get(f"/api/v1/student/items/{items[2].id}")
    assert resp_q3.status_code == 404

    # 8. Test Export endpoint
    resp_export = client.get(f"/api/v1/student/units/{unit.id}/export?format=html")
    assert resp_export.status_code == 200
    assert "text/html" in resp_export.headers["content-type"]
    assert "Student Test Unit" in resp_export.text
