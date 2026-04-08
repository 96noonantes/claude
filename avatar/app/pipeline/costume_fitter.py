"""Fit costumes from one body profile to another using affine transforms.

When a costume designed for body A is worn on body B, each part is scaled
and repositioned to match B's proportions.
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path

from app.models.session import BodyProfile, PartData


def fit_costume_to_body(
    parts: list[PartData],
    source_profile: BodyProfile,
    target_profile: BodyProfile,
    parts_dir: Path | None = None,
) -> list[PartData]:
    """Transform costume parts from source body to target body.

    Adjusts normalized_bounds, anchor, fit_points, and optionally warps
    the part images to match the target proportions.
    """
    result = []

    for part in parts:
        new_part = _transform_part(part, source_profile, target_profile)
        result.append(new_part)

    return result


def compute_body_scale(source: BodyProfile, target: BodyProfile) -> dict:
    """Compute scale factors between two body profiles.

    Returns dict with scale factors for each body region.
    Used by the frontend preview for real-time scaling.
    """
    def safe_div(a, b):
        return a / b if b > 0 else 1.0

    return {
        "height": round(safe_div(target.height, source.height), 4),
        "shoulder": round(safe_div(target.shoulder_width, source.shoulder_width), 4),
        "waist": round(safe_div(target.waist_width, source.waist_width), 4),
        "hip": round(safe_div(target.hip_width, source.hip_width), 4),
        "leg": round(safe_div(target.leg_ratio, source.leg_ratio), 4),
        "head": round(safe_div(target.head_ratio, source.head_ratio), 4),
    }


def _transform_part(
    part: PartData,
    source: BodyProfile,
    target: BodyProfile,
) -> PartData:
    """Transform a single part's coordinates to a new body profile."""
    import copy
    new = copy.deepcopy(part)

    if not part.fit_points:
        # No fit points: use simple proportional scaling
        scale = compute_body_scale(source, target)
        new.normalized_bounds = _scale_bounds(part.normalized_bounds, scale, part.category)
        new.anchor = _scale_point(part.anchor, scale, part.category)
        return new

    # Use fit points for precise transformation
    src_points = part.fit_points
    tgt_points = _compute_target_fit_points(src_points, source, target)
    new.fit_points = tgt_points

    # Compute transform from fit point pairs
    sx, sy, tx, ty = _fit_point_transform(src_points, tgt_points)

    if part.normalized_bounds:
        nb = part.normalized_bounds
        new.normalized_bounds = {
            "x": round(nb.get("x", 0) * sx + tx, 4),
            "y": round(nb.get("y", 0) * sy + ty, 4),
            "width": round(nb.get("width", 0) * sx, 4),
            "height": round(nb.get("height", 0) * sy, 4),
        }

    if part.anchor:
        new.anchor = {
            "x": round(part.anchor.get("x", 0) * sx + tx, 4),
            "y": round(part.anchor.get("y", 0) * sy + ty, 4),
        }

    return new


def _compute_target_fit_points(
    src_points: dict,
    source: BodyProfile,
    target: BodyProfile,
) -> dict:
    """Recompute fit points for the target body profile."""
    from app.pipeline.fit_points import FIT_POINT_TEMPLATES

    result = {}
    for name, src_pt in src_points.items():
        # Scale each fit point by the ratio of target/source body dimensions
        scale_x = target.shoulder_width / max(source.shoulder_width, 0.01)
        scale_y = target.height / max(source.height, 0.01)

        # Refine per-region scaling
        if "waist" in name:
            scale_x = target.waist_width / max(source.waist_width, 0.01)
        elif "hip" in name:
            scale_x = target.hip_width / max(source.hip_width, 0.01)
        elif "knee" in name or "ankle" in name:
            scale_y = target.leg_ratio / max(source.leg_ratio, 0.01)

        result[name] = {
            "x": round(src_pt.get("x", 0) * scale_x, 4),
            "y": round(src_pt.get("y", 0) * scale_y, 4),
        }

    return result


def _fit_point_transform(src_points: dict, tgt_points: dict) -> tuple:
    """Compute scale + translation from source fit points to target.

    Returns (scale_x, scale_y, translate_x, translate_y).
    """
    if not src_points or not tgt_points:
        return 1.0, 1.0, 0.0, 0.0

    src_xs = [p.get("x", 0) for p in src_points.values()]
    src_ys = [p.get("y", 0) for p in src_points.values()]
    tgt_xs = [tgt_points[k].get("x", 0) for k in src_points if k in tgt_points]
    tgt_ys = [tgt_points[k].get("y", 0) for k in src_points if k in tgt_points]

    if not tgt_xs:
        return 1.0, 1.0, 0.0, 0.0

    src_w = max(src_xs) - min(src_xs) if len(src_xs) > 1 else 1.0
    tgt_w = max(tgt_xs) - min(tgt_xs) if len(tgt_xs) > 1 else 1.0
    src_h = max(src_ys) - min(src_ys) if len(src_ys) > 1 else 1.0
    tgt_h = max(tgt_ys) - min(tgt_ys) if len(tgt_ys) > 1 else 1.0

    sx = tgt_w / src_w if src_w > 0.001 else 1.0
    sy = tgt_h / src_h if src_h > 0.001 else 1.0

    src_cx = sum(src_xs) / len(src_xs)
    src_cy = sum(src_ys) / len(src_ys)
    tgt_cx = sum(tgt_xs) / len(tgt_xs)
    tgt_cy = sum(tgt_ys) / len(tgt_ys)

    tx = tgt_cx - src_cx * sx
    ty = tgt_cy - src_cy * sy

    return round(sx, 4), round(sy, 4), round(tx, 4), round(ty, 4)


def _scale_bounds(bounds: dict, scale: dict, category: str) -> dict:
    if not bounds:
        return bounds

    # Choose scale based on category / body region
    if category in ("tops", "outer", "one_piece", "collar", "sleeve"):
        sx = scale.get("shoulder", 1.0)
    elif category in ("bottoms_skirt", "bottoms_pants"):
        sx = scale.get("hip", 1.0)
    elif category in ("socks", "shoes"):
        sx = scale.get("hip", 1.0) * 0.8  # legs scale less
    else:
        sx = (scale.get("shoulder", 1.0) + scale.get("hip", 1.0)) / 2

    sy = scale.get("height", 1.0)

    return {
        "x": round(bounds.get("x", 0) * sx, 4),
        "y": round(bounds.get("y", 0) * sy, 4),
        "width": round(bounds.get("width", 0) * sx, 4),
        "height": round(bounds.get("height", 0) * sy, 4),
    }


def _scale_point(point: dict, scale: dict, category: str) -> dict:
    if not point:
        return point
    sx = scale.get("shoulder", 1.0)
    sy = scale.get("height", 1.0)
    return {
        "x": round(point.get("x", 0) * sx, 4),
        "y": round(point.get("y", 0) * sy, 4),
    }
