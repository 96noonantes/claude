"""API for reading and adjusting the avatar's body profile."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.session import get_session

router = APIRouter()


class BodyProfileUpdate(BaseModel):
    height: Optional[float] = None
    body_type: Optional[str] = None
    shoulder_width: Optional[float] = None
    waist_width: Optional[float] = None
    hip_width: Optional[float] = None
    leg_ratio: Optional[float] = None
    hair_color: Optional[list] = None
    skin_color: Optional[list] = None


@router.get("/body-profile/{session_id}")
async def get_body_profile(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    return asdict(session.body_profile)


@router.put("/body-profile/{session_id}")
async def update_body_profile(session_id: str, update: BodyProfileUpdate):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")

    bp = session.body_profile
    if update.height is not None:
        bp.height = max(0.5, min(2.0, update.height))
    if update.body_type is not None and update.body_type in ("slim", "normal", "muscular", "curvy"):
        bp.body_type = update.body_type
    if update.shoulder_width is not None:
        bp.shoulder_width = max(0.1, min(0.6, update.shoulder_width))
    if update.waist_width is not None:
        bp.waist_width = max(0.1, min(0.5, update.waist_width))
    if update.hip_width is not None:
        bp.hip_width = max(0.1, min(0.6, update.hip_width))
    if update.leg_ratio is not None:
        bp.leg_ratio = max(0.3, min(0.7, update.leg_ratio))
    if update.hair_color is not None and len(update.hair_color) == 3:
        bp.hair_color = [max(0, min(255, int(c))) for c in update.hair_color]
    if update.skin_color is not None and len(update.skin_color) == 3:
        bp.skin_color = [max(0, min(255, int(c))) for c in update.skin_color]

    session.save()

    # Compute scale factors for frontend preview
    from app.pipeline.costume_fitter import compute_body_scale
    from app.models.session import BodyProfile
    default_bp = BodyProfile()
    scale = compute_body_scale(default_bp, bp)

    return {**asdict(bp), "scale_factors": scale}
