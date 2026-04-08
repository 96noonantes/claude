"""Compute fit points for costume parts.

Fit points are anchor positions on the body where a costume part attaches.
When fitting a costume to a different body, these points are used to compute
the affine transformation.
"""

from app.models.session import PartData, BodyProfile


# Fit point definitions per clothing category
# Values are in normalized body coordinates (relative to body_top, body_center_x, body_height)
FIT_POINT_TEMPLATES = {
    "outerwear_upper": {
        "shoulder_left": lambda bp: {"x": -bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "shoulder_right": lambda bp: {"x": bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": bp.head_ratio + 0.18},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": bp.head_ratio + 0.18},
    },
    "tops": {
        "shoulder_left": lambda bp: {"x": -bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "shoulder_right": lambda bp: {"x": bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": bp.head_ratio + 0.18},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": bp.head_ratio + 0.18},
    },
    "outerwear_lower": {
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "hip_left": lambda bp: {"x": -bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
        "hip_right": lambda bp: {"x": bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
    },
    "bottoms_skirt": {
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "hip_left": lambda bp: {"x": -bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
        "hip_right": lambda bp: {"x": bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
    },
    "bottoms_pants": {
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": 1.0 - bp.leg_ratio - 0.02},
        "knee_left": lambda bp: {"x": -bp.hip_width * 0.35, "y": 1.0 - bp.leg_ratio * 0.45},
        "knee_right": lambda bp: {"x": bp.hip_width * 0.35, "y": 1.0 - bp.leg_ratio * 0.45},
    },
    "sleeve": {
        "shoulder": lambda bp: {"x": 0.0, "y": bp.head_ratio + 0.02},
        "elbow": lambda bp: {"x": 0.0, "y": bp.head_ratio + 0.15},
        "wrist": lambda bp: {"x": 0.0, "y": bp.head_ratio + 0.28},
    },
    "collar": {
        "neck_left": lambda bp: {"x": -bp.shoulder_width * 0.3, "y": bp.head_ratio - 0.01},
        "neck_right": lambda bp: {"x": bp.shoulder_width * 0.3, "y": bp.head_ratio - 0.01},
    },
    "socks": {
        "knee": lambda bp: {"x": 0.0, "y": 1.0 - bp.leg_ratio * 0.45},
        "ankle": lambda bp: {"x": 0.0, "y": 1.0 - 0.05},
    },
    "shoes": {
        "ankle_left": lambda bp: {"x": -bp.hip_width * 0.25, "y": 1.0 - 0.05},
        "ankle_right": lambda bp: {"x": bp.hip_width * 0.25, "y": 1.0 - 0.05},
    },
    "hat": {
        "head_top": lambda bp: {"x": 0.0, "y": 0.0},
        "head_left": lambda bp: {"x": -bp.head_ratio * 0.6, "y": bp.head_ratio * 0.3},
        "head_right": lambda bp: {"x": bp.head_ratio * 0.6, "y": bp.head_ratio * 0.3},
    },
    "one_piece": {
        "shoulder_left": lambda bp: {"x": -bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "shoulder_right": lambda bp: {"x": bp.shoulder_width / 2, "y": bp.head_ratio + 0.02},
        "waist_left": lambda bp: {"x": -bp.waist_width / 2, "y": bp.head_ratio + 0.18},
        "waist_right": lambda bp: {"x": bp.waist_width / 2, "y": bp.head_ratio + 0.18},
        "hip_left": lambda bp: {"x": -bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
        "hip_right": lambda bp: {"x": bp.hip_width / 2, "y": 1.0 - bp.leg_ratio + 0.05},
    },
}


def compute_fit_points(part: PartData, body_profile: BodyProfile) -> dict:
    """Compute fit points for a part based on its category and body profile.

    Returns dict of {point_name: {"x": float, "y": float}} in normalized coords.
    """
    category = part.category
    if not category:
        return {}

    # Check for sleeve (left/right variants use same template)
    if category == "sleeve":
        template = FIT_POINT_TEMPLATES.get("sleeve", {})
    else:
        template = FIT_POINT_TEMPLATES.get(category, {})

    if not template:
        return {}

    result = {}
    for name, fn in template.items():
        point = fn(body_profile)
        result[name] = {
            "x": round(point["x"], 4),
            "y": round(point["y"], 4),
        }

    return result
