from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
FRONTEND_DIR = BASE_DIR / "frontend"

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_DIMENSION = 4096
TARGET_IMAGE_DIMENSION = 2048
