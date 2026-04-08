"""Region-based part segmentation using face landmarks and image analysis."""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path

from app.pipeline.face_detector import FaceLandmarks
from app.pipeline.part_labels import get_label_ja, get_depth_order
from app.models.session import PartData


def segment_parts(
    image_rgba: np.ndarray,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks,
    output_dir: Path,
) -> list[PartData]:
    """Segment image into parts based on face landmarks."""
    h, w = image_rgba.shape[:2]
    alpha_mask = no_bg[:, :, 3] > 128  # Character mask

    parts: list[PartData] = []
    part_counter = 0

    def _save_part(label: str, mask: np.ndarray) -> PartData | None:
        nonlocal part_counter
        if mask.sum() < 100:
            return None

        masked = no_bg.copy()
        masked[~mask] = [0, 0, 0, 0]

        feathered = _feather_edges(masked, mask)

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return None
        y1, y2 = np.argmax(rows), len(rows) - np.argmax(rows[::-1])
        x1, x2 = np.argmax(cols), len(cols) - np.argmax(cols[::-1])

        pad = 5
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        part_img = feathered[y1:y2, x1:x2]
        filename = f"{label}.png"
        Image.fromarray(part_img).save(output_dir / filename)

        part_counter += 1
        return PartData(
            id=f"part_{part_counter:03d}",
            label=label,
            label_ja=get_label_ja(label),
            bounds={"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
            depth_order=get_depth_order(label),
            visible=True,
            image_filename=filename,
        )

    fx, fy, fw, fh = landmarks.face_rect

    # --- Face ---
    face_mask = np.zeros((h, w), dtype=bool)
    face_ellipse_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        face_ellipse_mask,
        (landmarks.face_center_x, fy + int(fh * 0.5)),
        (fw // 2, int(fh * 0.55)),
        0, 0, 360, 255, -1,
    )
    face_mask = (face_ellipse_mask > 0) & alpha_mask

    # --- Eyes ---
    for side, eye_rect in [("left", landmarks.left_eye_rect), ("right", landmarks.right_eye_rect)]:
        ex, ey, ew, eh = eye_rect
        expand = int(max(ew, eh) * 0.3)
        eye_mask = _rect_mask(h, w, ex - expand, ey - expand, ew + expand * 2, eh + expand * 2) & alpha_mask
        p = _save_part(f"eye_{side}", eye_mask)
        if p:
            parts.append(p)

    # --- Eyebrows ---
    for side, brow_rect in [("left", landmarks.left_eyebrow_rect), ("right", landmarks.right_eyebrow_rect)]:
        bx, by, bw, bh = brow_rect
        expand = int(max(bw, bh) * 0.2)
        brow_mask = _rect_mask(h, w, bx - expand, by - expand, bw + expand * 2, bh + expand * 2) & alpha_mask
        p = _save_part(f"eyebrow_{side}", brow_mask)
        if p:
            parts.append(p)

    # --- Nose ---
    nx, ny, nw, nh = landmarks.nose_rect
    expand_n = int(max(nw, nh) * 0.3)
    nose_mask = _rect_mask(h, w, nx - expand_n, ny - expand_n, nw + expand_n * 2, nh + expand_n * 2) & alpha_mask
    p = _save_part("nose", nose_mask)
    if p:
        parts.append(p)

    # --- Mouth ---
    mx, my, mw, mh = landmarks.mouth_rect
    expand_m = int(max(mw, mh) * 0.3)
    mouth_mask = _rect_mask(h, w, mx - expand_m, my - expand_m, mw + expand_m * 2, mh + expand_m * 2) & alpha_mask
    p = _save_part("mouth", mouth_mask)
    if p:
        parts.append(p)

    # --- Face (excluding sub-parts) ---
    sub_parts_mask = np.zeros((h, w), dtype=bool)
    for side in ["left", "right"]:
        ex, ey, ew, eh = getattr(landmarks, f"{side}_eye_rect")
        sub_parts_mask |= _rect_mask(h, w, ex, ey, ew, eh)
        bx, by, bw, bh = getattr(landmarks, f"{side}_eyebrow_rect")
        sub_parts_mask |= _rect_mask(h, w, bx, by, bw, bh)
    sub_parts_mask |= _rect_mask(h, w, *landmarks.nose_rect)
    sub_parts_mask |= _rect_mask(h, w, *landmarks.mouth_rect)

    face_only_mask = face_mask & ~sub_parts_mask
    p = _save_part("face", face_only_mask)
    if p:
        parts.append(p)

    # --- Hair ---
    hair_mask = _detect_hair(image_rgba, no_bg, landmarks, alpha_mask, face_mask)

    hair_front_mask = hair_mask & face_mask
    p = _save_part("hair_front", hair_front_mask)
    if p:
        parts.append(p)

    hair_back_mask = hair_mask & ~face_mask
    hair_above = hair_back_mask.copy()
    hair_above[landmarks.face_bottom:, :] = False
    p = _save_part("hair_back", hair_above)
    if p:
        parts.append(p)

    hair_side_left = hair_back_mask.copy()
    hair_side_left[:, landmarks.face_center_x:] = False
    hair_side_left[:landmarks.face_top, :] = False
    p = _save_part("hair_side_left", hair_side_left)
    if p:
        parts.append(p)

    hair_side_right = hair_back_mask.copy()
    hair_side_right[:, :landmarks.face_center_x] = False
    hair_side_right[:landmarks.face_top, :] = False
    p = _save_part("hair_side_right", hair_side_right)
    if p:
        parts.append(p)

    # --- Body ---
    body_mask = alpha_mask & ~face_mask & ~hair_mask
    body_mask[:landmarks.face_top, :] = False
    p = _save_part("body", body_mask)
    if p:
        parts.append(p)

    parts.sort(key=lambda p: p.depth_order)
    return parts


def _rect_mask(h: int, w: int, rx: int, ry: int, rw: int, rh: int) -> np.ndarray:
    """Create a boolean mask for a rectangle region."""
    mask = np.zeros((h, w), dtype=bool)
    x1 = max(0, int(rx))
    y1 = max(0, int(ry))
    x2 = min(w, int(rx + rw))
    y2 = min(h, int(ry + rh))
    mask[y1:y2, x1:x2] = True
    return mask


def _detect_hair(
    image_rgba: np.ndarray,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks,
    alpha_mask: np.ndarray,
    face_mask: np.ndarray,
) -> np.ndarray:
    """Detect hair region using color analysis and position heuristics."""
    h, w = image_rgba.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect

    rgb = no_bg[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    hair_candidate = alpha_mask.copy()

    # Sample hair color from above the face
    sample_y1 = max(0, fy - int(fh * 0.3))
    sample_y2 = fy
    sample_x1 = max(0, landmarks.face_center_x - fw // 4)
    sample_x2 = min(w, landmarks.face_center_x + fw // 4)

    sample_region = hsv[sample_y1:sample_y2, sample_x1:sample_x2]
    sample_alpha = alpha_mask[sample_y1:sample_y2, sample_x1:sample_x2]

    if sample_alpha.sum() > 50:
        hair_pixels = sample_region[sample_alpha]
        median_h = np.median(hair_pixels[:, 0])
        median_s = np.median(hair_pixels[:, 1])

        h_range = 25
        s_range = 60
        lower = np.array([max(0, median_h - h_range), max(0, median_s - s_range), 30])
        upper = np.array([min(180, median_h + h_range), min(255, median_s + s_range), 255])

        color_mask = cv2.inRange(hsv, lower, upper) > 0
        hair_candidate = alpha_mask & color_mask
    else:
        above_face = np.zeros((h, w), dtype=bool)
        above_face[:fy + int(fh * 0.2), :] = True
        hair_candidate = alpha_mask & above_face

    # Exclude body region (below face)
    body_region = np.zeros((h, w), dtype=bool)
    body_region[landmarks.face_bottom + int(fh * 0.2):, :] = True

    face_interior = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        face_interior,
        (landmarks.face_center_x, fy + int(fh * 0.5)),
        (int(fw * 0.35), int(fh * 0.4)),
        0, 0, 360, 255, -1,
    )
    face_interior_mask = face_interior > 0

    hair_mask = hair_candidate & ~body_region & ~face_interior_mask

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    hair_uint8 = hair_mask.astype(np.uint8) * 255
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_CLOSE, kernel, iterations=2)
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_OPEN, kernel, iterations=1)
    hair_mask = hair_uint8 > 0

    return hair_mask


def _feather_edges(image_rgba: np.ndarray, mask: np.ndarray, radius: int = 3) -> np.ndarray:
    """Apply Gaussian feathering to the edges of a masked region."""
    result = image_rgba.copy()
    mask_uint8 = mask.astype(np.uint8) * 255
    blurred = cv2.GaussianBlur(mask_uint8, (radius * 2 + 1, radius * 2 + 1), radius)
    alpha_factor = blurred.astype(np.float32) / 255.0
    result[:, :, 3] = (result[:, :, 3].astype(np.float32) * alpha_factor).astype(np.uint8)
    return result
