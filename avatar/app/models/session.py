from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from app.config import WORKSPACE_DIR


@dataclass
class BodyProfile:
    """Avatar body proportions and appearance, measured from the source image."""
    height: float = 1.0             # height scale (1.0 = as-is)
    body_type: str = "normal"       # slim / normal / muscular / curvy
    head_ratio: float = 0.15        # head height / total height
    shoulder_width: float = 0.35    # shoulder width / total height
    waist_width: float = 0.25       # waist width / total height
    hip_width: float = 0.30         # hip width / total height
    leg_ratio: float = 0.50         # leg length / total height
    # Pixel measurements (for coordinate normalization)
    body_top: int = 0               # top of character (px)
    body_bottom: int = 0            # bottom of character (px)
    body_center_x: int = 0          # center X of character (px)
    body_height_px: int = 1         # total height in pixels
    # Appearance
    hair_color: list = field(default_factory=lambda: [128, 128, 128])
    skin_color: list = field(default_factory=lambda: [240, 210, 180])


@dataclass
class PartData:
    id: str                         # stable ID = label (e.g. "outerwear_upper")
    label: str
    label_ja: str
    bounds: dict                    # {x, y, width, height} in pixels
    depth_order: int
    visible: bool = True
    image_filename: str = ""
    category: str = ""              # clothing category (tops, bottoms_skirt, etc.)
    gender: str = "unisex"          # male / female / unisex
    # Normalized coordinates (body-relative, for cross-avatar compatibility)
    normalized_bounds: dict = field(default_factory=dict)  # {x, y, width, height} normalized
    anchor: dict = field(default_factory=dict)             # {x, y} normalized pivot point
    fit_points: dict = field(default_factory=dict)         # {name: {x, y}} normalized

    def image_path(self, session_dir: Path) -> Path:
        return session_dir / "parts" / self.image_filename


@dataclass
class SessionData:
    session_id: str
    original_filename: str = ""
    image_width: int = 0
    image_height: int = 0
    mode: str = "full"
    status: str = "uploaded"
    parts: list[PartData] = field(default_factory=list)
    body_profile: BodyProfile = field(default_factory=BodyProfile)
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
        bp_data = data.pop("body_profile", {})
        body_profile = BodyProfile(**bp_data) if bp_data else BodyProfile()
        return cls(**data, parts=parts, body_profile=body_profile)


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
