import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.session import get_session
from app.export.package_builder import build_export_package

router = APIRouter()


@router.post("/export/{session_id}")
async def create_export(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")
    if session.status != "done":
        raise HTTPException(400, "パーツ分解が完了していません")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, build_export_package, session)

    return {
        "download_url": f"/api/export/{session_id}/download",
        "filename": f"live2d_avatar_{session_id}.zip",
    }


@router.get("/export/{session_id}/download")
async def download_export(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "セッションが見つかりません")

    zip_path = session.dir / "export" / f"live2d_avatar_{session_id}.zip"
    if not zip_path.exists():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, build_export_package, session)

    if not zip_path.exists():
        raise HTTPException(500, "エクスポートファイルの生成に失敗しました")

    return FileResponse(
        path=str(zip_path),
        filename=f"live2d_avatar_{session_id}.zip",
        media_type="application/zip",
    )
