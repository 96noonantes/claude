from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import FRONTEND_DIR, WORKSPACE_DIR
from app.api.upload import router as upload_router
from app.api.decompose import router as decompose_router
from app.api.parts import router as parts_router
from app.api.export import router as export_router

app = FastAPI(title="Live2D Avatar Generator", version="1.0.0")

app.include_router(upload_router, prefix="/api")
app.include_router(decompose_router, prefix="/api")
app.include_router(parts_router, prefix="/api")
app.include_router(export_router, prefix="/api")

app.mount("/workspace", StaticFiles(directory=str(WORKSPACE_DIR)), name="workspace")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")
