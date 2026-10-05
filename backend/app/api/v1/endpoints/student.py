"""API endpoints for Student Mode (read-only, approved versions strictly enforced) and HTML/PDF export."""

import html
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.db.models.unit import Unit
from backend.app.db.models.content import Asset, Item, ItemVersion

router = APIRouter()


class StudentItemResponse(BaseModel):
    item_id: str
    asset_type: str
    item_type: str
    position: int
    version_id: str
    version_number: int
    content: dict
    objective_id: str
    source_chunk_ids: list[str]
    bloom_level: str | None


class StudentAssetResponse(BaseModel):
    asset_id: str
    asset_type: str
    items: list[StudentItemResponse]


class StudentUnitResponse(BaseModel):
    unit_id: str
    title: str
    target_level: str
    difficulty: str
    assets: list[StudentAssetResponse]


def get_approved_unit_content(db: Session, unit_id: str) -> dict:
    """Queries unit and returns ONLY items that have an Approved item_version.
    
    Items without an approved version are omitted.
    """
    unit = db.query(Unit).filter_by(id=unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{unit_id}' not found.")

    assets = db.query(Asset).filter_by(unit_id=unit.id).all()
    asset_responses = []

    for asset in assets:
        approved_items = []
        for item in asset.items:
            if item.current_approved_version_id:
                app_ver = (
                    db.query(ItemVersion)
                    .filter_by(id=item.current_approved_version_id, status="Approved")
                    .first()
                )
                if app_ver:
                    approved_items.append({
                        "item_id": item.id,
                        "asset_type": asset.asset_type,
                        "item_type": item.item_type,
                        "position": item.position,
                        "version_id": app_ver.id,
                        "version_number": app_ver.version_number,
                        "content": app_ver.content,
                        "objective_id": app_ver.objective_id,
                        "source_chunk_ids": app_ver.source_chunk_ids,
                        "bloom_level": app_ver.bloom_level,
                    })

        if approved_items:
            approved_items.sort(key=lambda x: x["position"])
            asset_responses.append({
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "items": approved_items,
            })

    return {
        "unit_id": unit.id,
        "title": unit.title,
        "target_level": unit.target_level,
        "difficulty": unit.difficulty,
        "assets": asset_responses,
    }


@router.get("/student/units/{id}", response_model=StudentUnitResponse)
def get_student_unit(id: str, db: Session = Depends(get_db)):
    """Retrieve student unit view containing approved items ONLY."""
    content = get_approved_unit_content(db, id)
    return StudentUnitResponse(
        unit_id=content["unit_id"],
        title=content["title"],
        target_level=content["target_level"],
        difficulty=content["difficulty"],
        assets=[
            StudentAssetResponse(
                asset_id=a["asset_id"],
                asset_type=a["asset_type"],
                items=[StudentItemResponse(**it) for it in a["items"]],
            )
            for a in content["assets"]
        ],
    )


@router.get("/student/items/{id}", response_model=StudentItemResponse)
def get_student_item(id: str, db: Session = Depends(get_db)):
    """Retrieve approved version for an item by direct ID. Returns 404 if item has no approved version."""
    item = db.query(Item).filter_by(id=id).first()
    if not item or not item.current_approved_version_id:
        raise HTTPException(status_code=404, detail=f"Approved item '{id}' not found.")

    app_ver = (
        db.query(ItemVersion)
        .filter_by(id=item.current_approved_version_id, status="Approved")
        .first()
    )
    if not app_ver:
        raise HTTPException(status_code=404, detail=f"Approved item '{id}' not found.")

    return StudentItemResponse(
        item_id=item.id,
        asset_type=item.asset.asset_type,
        item_type=item.item_type,
        position=item.position,
        version_id=app_ver.id,
        version_number=app_ver.version_number,
        content=app_ver.content,
        objective_id=app_ver.objective_id,
        source_chunk_ids=app_ver.source_chunk_ids,
        bloom_level=app_ver.bloom_level,
    )


@router.get("/student/units/{id}/export")
def export_student_unit(id: str, format: str = Query("html", enum=["html", "pdf"]), db: Session = Depends(get_db)):
    """Export student approved content as HTML or PDF."""
    unit_data = get_approved_unit_content(db, id)

    # Render HTML document
    html_lines = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{html.escape(unit_data['title'])} - Student Pack</title>",
        "<style>",
        "body { font-family: system-ui, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }",
        "h1 { color: #2b6cb0; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }",
        "h2 { color: #2d3748; margin-top: 30px; border-left: 4px solid #4299e1; padding-left: 10px; }",
        ".item-card { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 15px; }",
        ".option { margin: 5px 0; padding: 5px 10px; background: #ffffff; border: 1px solid #cbd5e0; border-radius: 4px; }",
        ".tag { font-size: 0.8em; background: #e2e8f0; color: #4a5568; padding: 2px 6px; border-radius: 4px; }",
        "</style></head><body>",
        f"<h1>{html.escape(unit_data['title'])}</h1>",
        f"<p><strong>Target Level:</strong> {html.escape(unit_data['target_level'])} | <strong>Difficulty:</strong> {html.escape(unit_data['difficulty'])}</p>",
    ]

    for asset in unit_data["assets"]:
        asset_title = asset["asset_type"].replace("_", " ").title()
        html_lines.append(f"<h2>{html.escape(asset_title)}</h2>")

        for item in asset["items"]:
            c = item["content"]
            html_lines.append("<div class='item-card'>")
            if "heading" in c:
                html_lines.append(f"<h3>{html.escape(c['heading'])}</h3>")
            if "body" in c:
                html_lines.append(f"<p>{html.escape(c['body'])}</p>")
            if "stem" in c:
                html_lines.append(f"<p><strong>Q: {html.escape(c['stem'])}</strong></p>")
            if "options" in c:
                for opt in c["options"]:
                    html_lines.append(f"<div class='option'><strong>{opt['label']}:</strong> {html.escape(opt['text'])}</div>")
            if "prompt" in c:
                html_lines.append(f"<p><strong>Prompt:</strong> {html.escape(c['prompt'])}</p>")
            if "point" in c:
                html_lines.append(f"<p>• {html.escape(c['point'])}</p>")
            if "instruction" in c:
                html_lines.append(f"<p><strong>Step {c.get('step_number', '')}:</strong> {html.escape(c['instruction'])}</p>")
                if "working" in c:
                    html_lines.append(f"<p><em>Working:</em> {html.escape(c['working'])}</p>")

            html_lines.append(f"<span class='tag'>Objective: {html.escape(item['objective_id'])}</span>")
            html_lines.append("</div>")

    html_lines.append("</body></html>")
    full_html = "\n".join(html_lines)

    if format == "html":
        return Response(content=full_html, media_type="text/html")
    else:
        # PDF format fallback / export
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=full_html).write_pdf()
            return Response(content=pdf_bytes, media_type="application/pdf")
        except Exception:
            # Fallback if weasyprint system library is missing
            return Response(content=full_html, media_type="text/html", headers={"X-Export-Fallback": "HTML due to PDF rendering engine missing"})
