from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image

from app.config import MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS, MAX_IMAGE_DIMENSION
from app.models.session import create_session

router = APIRouter()


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"非対応の画像形式です。対応形式: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"ファイルサイズが大きすぎます（最大{MAX_UPLOAD_SIZE // 1024 // 1024}MB）")

    session = create_session()

    image_path = session.original_image_path
    image_path.write_bytes(content)

    try:
        with Image.open(image_path) as img:
            if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
                raise HTTPException(400, f"画像サイズが大きすぎます（最大{MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px）")
            session.image_width = img.width
            session.image_height = img.height
            img.save(image_path, "PNG")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "画像ファイルを読み込めませんでした")

    session.original_filename = file.filename or "image.png"
    session.status = "uploaded"
    session.save()

    return {
        "session_id": session.session_id,
        "original_image_url": f"/workspace/{session.session_id}/original.png",
        "width": session.image_width,
        "height": session.image_height,
    }
