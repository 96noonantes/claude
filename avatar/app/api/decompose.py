import asyncio
import threading

from fastapi import APIRouter, HTTPException

from app.models.session import get_session
from app.pipeline.decomposer import run_decomposition

router = APIRouter()

_session_locks: dict[str, threading.Lock] = {}


def _get_session_lock(session_id: str) -> threading.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = threading.Lock()
    return _session_locks[session_id]


@router.post("/decompose/{session_id}")
async def decompose_image(session_id: str, mode: str = "full"):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status == "processing":
        raise HTTPException(409, "処理中です")
    if mode not in ("full", "costume_only"):
        raise HTTPException(400, "モードは 'full' または 'costume_only' を指定してください")

    session.mode = mode
    session.status = "processing"
    session.error_message = ""
    session.parts = []
    session.save()

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _decompose_sync, session_id)

    return {"status": "processing", "session_id": session_id, "mode": mode}


def _decompose_sync(session_id: str):
    lock = _get_session_lock(session_id)
    with lock:
        from app.models.session import get_session as _get
        session = _get(session_id)
        if not session:
            return
        try:
            parts, body_profile = run_decomposition(session.original_image_path, session.parts_dir, mode=session.mode)
            session.parts = parts
            session.body_profile = body_profile
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
