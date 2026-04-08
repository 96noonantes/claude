"""Auto-rigging: assign deformers and vertex weights to mesh parts.

Maps each part's category to deformer definitions (rotation, scale, translate,
bezier chain) and computes per-vertex influence weights.
"""

import math
import numpy as np
from dataclasses import dataclass, field, asdict


@dataclass
class Deformer:
    type: str              # "rotation", "scale_y", "scale_x", "translate", "chain"
    param: str             # animation parameter name (e.g., "eyeLOpen")
    pivot: list            # [x, y] in 0-1 normalized coords within the part
    scale: float = 1.0     # multiplier for parameter → displacement
    weights: list = field(default_factory=list)  # per-vertex weight (0-1)


def auto_rig(part_id: str, category: str, label: str, mesh_vertices: list) -> list[dict]:
    """Generate deformer definitions for a part based on its category.

    Returns list of deformer dicts ready for JSON serialization.
    """
    n = len(mesh_vertices)
    if n == 0:
        return []

    verts = np.array(mesh_vertices, dtype=float)
    # Normalize to 0-1
    vmin = verts.min(axis=0)
    vmax = verts.max(axis=0)
    vrange = vmax - vmin
    vrange[vrange < 1] = 1
    norm = (verts - vmin) / vrange

    deformers = []

    # --- Face: rotation around neck ---
    if category == "face" or label == "face":
        deformers.extend([
            _rotation("angleX", [0.5, 0.95], 0.5, norm, radius=1.0),
            _rotation("angleY", [0.5, 0.95], 0.3, norm, radius=1.0),
            _rotation("angleZ", [0.5, 0.95], 0.3, norm, radius=1.0),
        ])

    # --- Eyes: blink (scaleY) ---
    elif label in ("eye_left", "eye_white_left"):
        deformers.append(_scale_y("eyeLOpen", [0.5, 0.5], 1.0, norm))
        deformers.append(_scale_y("eyeLSmile", [0.5, 0.3], -0.3, norm))
    elif label in ("eye_right", "eye_white_right"):
        deformers.append(_scale_y("eyeROpen", [0.5, 0.5], 1.0, norm))
        deformers.append(_scale_y("eyeRSmile", [0.5, 0.3], -0.3, norm))

    # --- Iris: eye tracking ---
    elif label == "iris_left":
        deformers.append(_translate("eyeBallX", [0.5, 0.5], 0.15, "x", norm))
        deformers.append(_translate("eyeBallY", [0.5, 0.5], 0.1, "y", norm))
    elif label == "iris_right":
        deformers.append(_translate("eyeBallX", [0.5, 0.5], 0.15, "x", norm))
        deformers.append(_translate("eyeBallY", [0.5, 0.5], 0.1, "y", norm))

    # --- Eyebrows ---
    elif label == "eyebrow_left":
        deformers.append(_translate("browLY", [0.5, 0.5], 0.3, "y", norm))
        deformers.append(_rotation("browLAngle", [0.5, 0.5], 5.0, norm, radius=1.0))
    elif label == "eyebrow_right":
        deformers.append(_translate("browRY", [0.5, 0.5], 0.3, "y", norm))
        deformers.append(_rotation("browRAngle", [0.5, 0.5], -5.0, norm, radius=1.0))

    # --- Mouth ---
    elif label == "mouth":
        deformers.append(_scale_y("mouthOpenY", [0.5, 0.3], 0.5, norm))
        deformers.append(_scale_x("mouthForm", [0.5, 0.5], 0.15, norm))

    # --- Nose ---
    elif label == "nose":
        deformers.extend([
            _rotation("angleX", [0.5, 0.8], 0.3, norm, radius=1.0),
            _rotation("angleY", [0.5, 0.8], 0.2, norm, radius=1.0),
        ])

    # --- Neck ---
    elif label == "neck":
        deformers.append(_rotation("angleX", [0.5, 0.0], 0.2, norm, radius=1.0))

    # --- Ears (follow head) ---
    elif label.startswith("ear"):
        deformers.append(_rotation("angleX", [0.5, 0.5], 0.4, norm, radius=1.0))

    # --- Body: breathing ---
    elif category == "body" or label in ("body", "body_skin"):
        deformers.append(_scale_y("breath", [0.5, 0.3], 0.015, norm))
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.3, "x", norm))

    # --- Hair: pendulum chain (root fixed, tip free) ---
    elif category == "hair":
        param = _hair_param(label)
        deformers.append(_chain(param, norm, root_y=0.0))

    # --- Outerwear upper: follow body ---
    elif label == "outerwear_upper" or category == "tops":
        deformers.append(_scale_y("breath", [0.5, 0.3], 0.01, norm))
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.2, "x", norm))

    # --- Outerwear lower (skirt/pants): pendulum ---
    elif label == "outerwear_lower" or category in ("bottoms_skirt", "bottoms_pants"):
        deformers.append(_chain("skirtCenter", norm, root_y=0.0))
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.15, "x", norm))

    # --- Sleeves ---
    elif category == "sleeve" or label.startswith("sleeve"):
        deformers.append(_scale_y("breath", [0.5, 0.3], 0.008, norm))

    # --- Collar ---
    elif category == "collar" or label == "collar":
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.15, "x", norm))

    # --- Arms ---
    elif category == "limb" and ("arm" in label or "hand" in label or "finger" in label):
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.15, "x", norm))
        swing_sign = 1.0 if "left" in label else -1.0
        deformers.append(_rotation("bodyAngleX", [0.5, 0.0], swing_sign * 0.8, norm, radius=1.0))

    # --- Legs ---
    elif category == "limb" and ("thigh" in label or "shin" in label or "foot" in label or "leg" in label):
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.1, "x", norm))

    # --- Legwear, shoes ---
    elif category in ("socks", "shoes"):
        deformers.append(_translate("bodyAngleX", [0.5, 0.5], 0.1, "x", norm))

    # --- Head accessories: follow head ---
    elif category in ("hat", "accessory"):
        deformers.append(_rotation("angleX", [0.5, 0.8], 0.4, norm, radius=1.0))
        deformers.append(_rotation("angleZ", [0.5, 0.8], 0.2, norm, radius=1.0))

    # Serialize
    return [asdict(d) for d in deformers]


# --- Deformer constructors ---

def _rotation(param, pivot, scale, norm_verts, radius=1.0):
    weights = _radial_weights(norm_verts, pivot, radius)
    return Deformer("rotation", param, pivot, scale, weights)


def _scale_y(param, pivot, scale, norm_verts):
    weights = _box_weights(norm_verts)
    return Deformer("scale_y", param, pivot, scale, weights)


def _scale_x(param, pivot, scale, norm_verts):
    weights = _box_weights(norm_verts)
    return Deformer("scale_x", param, pivot, scale, weights)


def _translate(param, pivot, scale, axis, norm_verts):
    weights = _uniform_weights(len(norm_verts))
    dtype = f"translate_{axis}"
    return Deformer(dtype, param, pivot, scale, weights)


def _chain(param, norm_verts, root_y=0.0):
    """Chain deformer: weight increases from root to tip (y-direction)."""
    n = len(norm_verts)
    weights = []
    for v in norm_verts:
        # Weight = distance from root along Y (0 at root, 1 at tip)
        w = abs(v[1] - root_y)
        weights.append(round(min(1.0, w), 3))
    return Deformer("chain", param, [0.5, root_y], 1.0, weights)


# --- Weight computation ---

def _radial_weights(norm_verts, pivot, radius):
    """Radial falloff from pivot."""
    px, py = pivot
    weights = []
    for v in norm_verts:
        d = math.sqrt((v[0] - px) ** 2 + (v[1] - py) ** 2)
        w = max(0.0, 1.0 - (d / radius) ** 2)
        weights.append(round(w, 3))
    return weights


def _box_weights(norm_verts):
    """Uniform weight inside, tapered at edges."""
    weights = []
    for v in norm_verts:
        # Distance from edge (0 = edge, 0.5 = center)
        edge_dist = min(v[0], 1.0 - v[0], v[1], 1.0 - v[1])
        w = min(1.0, edge_dist * 5.0)  # ramp up in first 20% from edge
        weights.append(round(w, 3))
    return weights


def _uniform_weights(n):
    return [1.0] * n


def _hair_param(label):
    mapping = {
        "hair_front": "hairFront",
        "hair_back": "hairBack",
        "hair_side_left": "hairSideL",
        "hair_side_right": "hairSideR",
    }
    return mapping.get(label, "hairFront")
