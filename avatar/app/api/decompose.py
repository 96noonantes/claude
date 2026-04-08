import asyncio

from fastapi import APIRouter, HTTPException

from app.models.session import get_session
from app.pipeline.decomposer import run_decomposition

router = APIRouter()


@router.post("/decompose/{session_id}")
async def decompose_image(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status == "processing":
        raise HTTPException(409, "処理中です")

    session.status = "processing"
    session.save()

    asyncio.get_event_loop().run_in_executor(None, _decompose_sync, session_id)

    return {"status": "processing", "session_id": session_id}


def _decompose_sync(session_id: str):
    from app.models.session import get_session as _get
    session = _get(session_id)
    if not session:
        return
    try:
        parts = run_decomposition(session.original_image_path, session.parts_dir)
        session.parts = parts
        session.status = "done"
    except Exception as e:
        session.status = "error"
        session.error_message = str(e)
    session.save()


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    return {
        "status": session.status,
        "error_message": session.error_message,
        "parts_count": len(session.parts),
    }
