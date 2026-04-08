"""API for serving runtime model data (mesh + atlas + deformers) to WebGL renderer."""

from collections import OrderedDict

from fastapi import APIRouter, HTTPException

from app.models.session import get_session
from app.export.runtime_exporter import generate_runtime_data

router = APIRouter()

# LRU cache (max 20 sessions)
_MAX_CACHE = 20
_runtime_cache: OrderedDict[str, dict] = OrderedDict()


def invalidate_cache(session_id: str) -> None:
    """Call when session data changes to clear stale cache."""
    _runtime_cache.pop(session_id, None)


@router.get("/runtime-data/{session_id}")
async def get_runtime_data(session_id: str):
    """Get avatar runtime data for WebGL rendering."""
    if session_id in _runtime_cache:
        _runtime_cache.move_to_end(session_id)
        return _runtime_cache[session_id]

    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status != "done":
        raise HTTPException(400, "パーツ分解が完了していません")
    if not session.parts:
        raise HTTPException(400, "パーツが存在しません")

    runtime_data, atlas_image = generate_runtime_data(session)

    # Save atlas to workspace for WebGL texture loading
    atlas_dir = session.dir / "export"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    atlas_image.save(atlas_dir / "atlas.png")

    # Cache with LRU eviction
    _runtime_cache[session_id] = runtime_data
    while len(_runtime_cache) > _MAX_CACHE:
        _runtime_cache.popitem(last=False)

    return runtime_data
