"""Analyze character image to extract body proportions (BodyProfile).

Measures body shape from the alpha mask and face landmarks:
head ratio, shoulder/waist/hip widths, leg length, hair/skin colors.
"""

import cv2
import numpy as np

from app.models.session import BodyProfile, PartData
from app.pipeline.face_detector import FaceLandmarks


def analyze_body(
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    parts: list[PartData],
) -> BodyProfile:
    """Extract BodyProfile from the character image."""
    h, w = no_bg.shape[:2]
    alpha = no_bg[:, :, 3] > 128

    rows = np.any(alpha, axis=1)
    if not rows.any():
        return BodyProfile()

    body_top = int(np.argmax(rows))
    body_bottom = int(len(rows) - np.argmax(rows[::-1]))
    body_height_px = max(1, body_bottom - body_top)

    cols = np.any(alpha, axis=0)
    body_left = int(np.argmax(cols))
    body_right = int(len(cols) - np.argmax(cols[::-1]))
    body_center_x = (body_left + body_right) // 2

    profile = BodyProfile(
        body_top=body_top,
        body_bottom=body_bottom,
        body_center_x=body_center_x,
        body_height_px=body_height_px,
    )

    # --- Head ratio ---
    if landmarks:
        fx, fy, fw, fh = landmarks.face_rect
        profile.head_ratio = round(fh / body_height_px, 3)
    else:
        profile.head_ratio = 0.15

    # --- Shoulder width ---
    if landmarks:
        shoulder_y = landmarks.face_bottom + int(body_height_px * 0.03)
    else:
        shoulder_y = body_top + int(body_height_px * 0.22)
    shoulder_y = min(shoulder_y, h - 1)
    shoulder_w = int(np.sum(alpha[shoulder_y, :]))
    profile.shoulder_width = round(shoulder_w / body_height_px, 3)

    # --- Waist width ---
    if landmarks:
        waist_y = landmarks.face_bottom + int(body_height_px * 0.15)
    else:
        waist_y = body_top + int(body_height_px * 0.45)
    waist_y = min(waist_y, h - 1)
    waist_w = int(np.sum(alpha[waist_y, :]))
    profile.waist_width = round(waist_w / body_height_px, 3)

    # --- Hip width ---
    if landmarks:
        hip_y = landmarks.face_bottom + int(body_height_px * 0.25)
    else:
        hip_y = body_top + int(body_height_px * 0.55)
    hip_y = min(hip_y, h - 1)
    hip_w = int(np.sum(alpha[hip_y, :]))
    profile.hip_width = round(hip_w / body_height_px, 3)

    # --- Leg ratio ---
    if landmarks:
        leg_top = landmarks.face_bottom + int(body_height_px * 0.30)
    else:
        leg_top = body_top + int(body_height_px * 0.50)
    profile.leg_ratio = round((body_bottom - leg_top) / body_height_px, 3)

    # --- Body type inference ---
    if profile.shoulder_width > 0:
        whr = profile.waist_width / profile.shoulder_width
        if whr < 0.65:
            profile.body_type = "curvy"
        elif whr < 0.78:
            profile.body_type = "normal"
        elif profile.shoulder_width > 0.40:
            profile.body_type = "muscular"
        else:
            profile.body_type = "slim"

    # --- Hair color (median of hair parts) ---
    hair_labels = {"hair_front", "hair_back", "hair_side_left", "hair_side_right"}
    hair_pixels = _collect_part_pixels(no_bg, parts, hair_labels)
    if hair_pixels.shape[0] > 50:
        profile.hair_color = [int(np.median(hair_pixels[:, c])) for c in range(3)]

    # --- Skin color (from face region) ---
    if landmarks:
        fx, fy, fw, fh = landmarks.face_rect
        ycrcb = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2YCrCb)
        sy = fy + int(fh * 0.45)
        sh = int(fh * 0.15)
        for sx1, sx2 in [(body_center_x - int(fw * 0.3), body_center_x - int(fw * 0.1)),
                          (body_center_x + int(fw * 0.1), body_center_x + int(fw * 0.3))]:
            sx1 = max(0, sx1)
            sx2 = min(w, sx2)
            region = no_bg[sy:sy+sh, sx1:sx2]
            region_a = alpha[sy:sy+sh, sx1:sx2]
            if region_a.sum() > 10:
                skin = region[region_a][:, :3]
                profile.skin_color = [int(np.median(skin[:, c])) for c in range(3)]
                break

    return profile


def normalize_part_bounds(
    part: PartData,
    profile: BodyProfile,
) -> dict:
    """Convert pixel bounds to body-normalized coordinates."""
    bh = max(1, profile.body_height_px)
    cx = profile.body_center_x
    top = profile.body_top

    px = part.bounds.get("x", 0)
    py = part.bounds.get("y", 0)
    pw = part.bounds.get("width", 0)
    ph = part.bounds.get("height", 0)

    return {
        "x": round((px - cx) / bh, 4),
        "y": round((py - top) / bh, 4),
        "width": round(pw / bh, 4),
        "height": round(ph / bh, 4),
    }


def compute_anchor(part: PartData, profile: BodyProfile) -> dict:
    """Compute normalized anchor (center) for a part."""
    bh = max(1, profile.body_height_px)
    cx = profile.body_center_x
    top = profile.body_top

    px = part.bounds.get("x", 0) + part.bounds.get("width", 0) / 2
    py = part.bounds.get("y", 0) + part.bounds.get("height", 0) / 2

    return {
        "x": round((px - cx) / bh, 4),
        "y": round((py - top) / bh, 4),
    }


def _collect_part_pixels(no_bg: np.ndarray, parts: list[PartData], labels: set) -> np.ndarray:
    """Collect RGB pixels from parts matching given labels."""
    h, w = no_bg.shape[:2]
    all_pixels = []
    for p in parts:
        if p.label not in labels:
            continue
        bx = p.bounds.get("x", 0)
        by = p.bounds.get("y", 0)
        bw = p.bounds.get("width", 0)
        bh_p = p.bounds.get("height", 0)
        y1 = max(0, by)
        y2 = min(h, by + bh_p)
        x1 = max(0, bx)
        x2 = min(w, bx + bw)
        region = no_bg[y1:y2, x1:x2]
        mask = region[:, :, 3] > 128
        if mask.sum() > 0:
            all_pixels.append(region[mask][:, :3])
    if all_pixels:
        return np.concatenate(all_pixels)
    return np.empty((0, 3), dtype=np.uint8)
