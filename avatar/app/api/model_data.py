"""API for serving runtime model data (mesh + atlas + deformers) to WebGL renderer."""

from fastapi import APIRouter, HTTPException

from app.models.session import get_session
from app.export.runtime_exporter import generate_runtime_data

router = APIRouter()

# Cache to avoid regenerating on every request
_runtime_cache: dict[str, dict] = {}


@router.get("/runtime-data/{session_id}")
async def get_runtime_data(session_id: str):
    """Get avatar runtime data for WebGL rendering.

    Returns JSON with mesh, atlas UVs, deformers, parameters, physics,
    motions, expressions — everything the PWA needs.
    """
    if session_id in _runtime_cache:
        return _runtime_cache[session_id]

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status != "done":
        raise HTTPException(400, "パーツ分解が完了していません")

    runtime_data, atlas_image = generate_runtime_data(session)

    # Save atlas to workspace for WebGL texture loading
    atlas_dir = session.dir / "export"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    atlas_image.save(atlas_dir / "atlas.png")

    _runtime_cache[session_id] = runtime_data
    return runtime_data
