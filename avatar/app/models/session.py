from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from app.config import WORKSPACE_DIR


@dataclass
class PartData:
    id: str
    label: str
    label_ja: str
    bounds: dict  # {x, y, width, height}
    depth_order: int
    visible: bool = True
    image_filename: str = ""

    def image_path(self, session_dir: Path) -> Path:
        return session_dir / "parts" / self.image_filename


@dataclass
class SessionData:
    session_id: str
    original_filename: str = ""
    image_width: int = 0
    image_height: int = 0
    mode: str = "full"  # "full" = all parts, "costume_only" = clothing extraction only
    status: str = "uploaded"  # uploaded -> processing -> done -> error
    parts: list[PartData] = field(default_factory=list)
    error_message: str = ""

    @property
    def dir(self) -> Path:
        return WORKSPACE_DIR / self.session_id

    @property
    def original_image_path(self) -> Path:
        return self.dir / "original.png"

    @property
    def parts_dir(self) -> Path:
        return self.dir / "parts"

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with open(self.dir / "session.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, session_id: str) -> Optional[SessionData]:
        path = WORKSPACE_DIR / session_id / "session.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        parts = [PartData(**p) for p in data.pop("parts", [])]
        return cls(**data, parts=parts)


# In-memory session store
_sessions: dict[str, SessionData] = {}


def create_session() -> SessionData:
    session_id = uuid.uuid4().hex[:12]
    session = SessionData(session_id=session_id)
    session.dir.mkdir(parents=True, exist_ok=True)
    session.parts_dir.mkdir(parents=True, exist_ok=True)
    _sessions[session_id] = session
    session.save()
    return session


def get_session(session_id: str) -> Optional[SessionData]:
    if session_id in _sessions:
        return _sessions[session_id]
    session = SessionData.load(session_id)
    if session:
        _sessions[session_id] = session
    return session
