from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.session import get_session

router = APIRouter()


class PartUpdate(BaseModel):
    visible: Optional[bool] = None
    label: Optional[str] = None
    bounds: Optional[dict] = None


@router.get("/parts/{session_id}")
async def get_parts(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status not in ("done",):
        raise HTTPException(400, f"パーツ分解が完了していません（状態: {session.status}）")

    parts_data = []
    for part in session.parts:
        d = asdict(part)
        d["image_url"] = f"/workspace/{session_id}/parts/{part.image_filename}"
        parts_data.append(d)

    return {"session_id": session_id, "parts": parts_data}


@router.put("/parts/{session_id}/{part_id}")
async def update_part(session_id: str, part_id: str, update: PartUpdate):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")

    part = next((p for p in session.parts if p.id == part_id), None)
    if not part:
        raise HTTPException(404, "パーツが見つかりません")

    if update.visible is not None:
        part.visible = update.visible
    if update.label is not None:
        part.label = update.label
    if update.bounds is not None:
        part.bounds = update.bounds

    session.save()
    d = asdict(part)
    d["image_url"] = f"/workspace/{session_id}/parts/{part.image_filename}"
    return d
