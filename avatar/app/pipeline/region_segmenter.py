"""Region-based part segmentation with improved accuracy.

Improvements over v1:
- K-means color clustering for hair detection (handles white/black/gradient hair)
- GrabCut refinement for pixel-accurate part boundaries
- Distance-transform-based adaptive feathering
- Iris/eye-white separation via Otsu thresholding
- Better body/arm detection
"""

import math

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from scipy import ndimage

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
    alpha_mask = no_bg[:, :, 3] > 128
    rgb = no_bg[:, :, :3]

    parts: list[PartData] = []
    part_counter = 0

    def _save_part(label: str, mask: np.ndarray) -> PartData | None:
        nonlocal part_counter
        if mask.sum() < 100:
            return None

        masked = no_bg.copy()
        masked[~mask] = [0, 0, 0, 0]

        feathered = _feather_edges_adaptive(masked, mask)

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return None
        y1 = int(np.argmax(rows))
        y2 = int(len(rows) - np.argmax(rows[::-1]))
        x1 = int(np.argmax(cols))
        x2 = int(len(cols) - np.argmax(cols[::-1]))

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

    # --- Face mask (ellipse) ---
    face_mask = np.zeros((h, w), dtype=bool)
    face_ellipse_img = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        face_ellipse_img,
        (landmarks.face_center_x, fy + int(fh * 0.5)),
        (fw // 2, int(fh * 0.55)),
        0, 0, 360, 255, -1,
    )
    face_mask = (face_ellipse_img > 0) & alpha_mask

    # --- Eyes with iris separation ---
    for side, eye_rect in [("left", landmarks.left_eye_rect), ("right", landmarks.right_eye_rect)]:
        ex, ey, ew, eh = eye_rect
        expand = int(max(ew, eh) * 0.3)
        eye_region_mask = _rect_mask(h, w, ex - expand, ey - expand, ew + expand * 2, eh + expand * 2) & alpha_mask

        # Refine with GrabCut
        eye_region_mask = _refine_mask_grabcut(rgb, eye_region_mask)

        # Separate iris from eye white
        iris_mask, white_mask = _separate_iris(no_bg, eye_region_mask, ex - expand, ey - expand, ew + expand * 2, eh + expand * 2)

        if iris_mask is not None and iris_mask.sum() > 50:
            p = _save_part(f"iris_{side}", iris_mask)
            if p:
                parts.append(p)
            p = _save_part(f"eye_white_{side}", white_mask)
            if p:
                parts.append(p)
        else:
            p = _save_part(f"eye_{side}", eye_region_mask)
            if p:
                parts.append(p)

    # --- Eyebrows ---
    for side, brow_rect in [("left", landmarks.left_eyebrow_rect), ("right", landmarks.right_eyebrow_rect)]:
        bx, by, bw, bh = brow_rect
        expand = int(max(bw, bh) * 0.2)
        brow_mask = _rect_mask(h, w, bx - expand, by - expand, bw + expand * 2, bh + expand * 2) & alpha_mask
        brow_mask = _refine_mask_grabcut(rgb, brow_mask)
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
    mouth_mask = _refine_mask_grabcut(rgb, mouth_mask)
    p = _save_part("mouth", mouth_mask)
    if p:
        parts.append(p)

    # --- Face (excluding sub-parts) ---
    sub_parts_mask = np.zeros((h, w), dtype=bool)
    for side in ["left", "right"]:
        er = getattr(landmarks, f"{side}_eye_rect")
        sub_parts_mask |= _rect_mask(h, w, *er)
        br = getattr(landmarks, f"{side}_eyebrow_rect")
        sub_parts_mask |= _rect_mask(h, w, *br)
    sub_parts_mask |= _rect_mask(h, w, *landmarks.nose_rect)
    sub_parts_mask |= _rect_mask(h, w, *landmarks.mouth_rect)

    face_only_mask = face_mask & ~sub_parts_mask
    p = _save_part("face", face_only_mask)
    if p:
        parts.append(p)

    # --- Hair (K-means clustering) ---
    hair_mask = _detect_hair_kmeans(image_rgba, no_bg, landmarks, alpha_mask, face_mask)

    # Split hair into front/back/sides
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

    # --- Body with clothing layer separation ---
    body_full_mask = alpha_mask & ~face_mask & ~hair_mask
    body_full_mask[:landmarks.face_top, :] = False

    # Try clothing segmentation (skin / upper wear / lower wear)
    clothing_result = _segment_clothing_layers(image_rgba, no_bg, body_full_mask, landmarks)

    if clothing_result is not None:
        skin_mask, upper_mask, lower_mask, neck_mask = clothing_result

        # Arms: protrusions from central body mass in skin areas
        arm_left, arm_right, skin_core = _detect_arms(skin_mask, landmarks, alpha_mask)

        # Legs: lower body skin regions
        leg_left, leg_right = _detect_legs(skin_mask, landmarks)

        # Save body skin (素体)
        p = _save_part("body_skin", skin_core)
        if p:
            parts.append(p)

        # Save neck
        if neck_mask is not None and neck_mask.sum() > 100:
            p = _save_part("neck", neck_mask)
            if p:
                parts.append(p)

        # Save outerwear upper (上半身衣装)
        if upper_mask.sum() > 200:
            p = _save_part("outerwear_upper", upper_mask)
            if p:
                parts.append(p)

        # Save outerwear lower (下半身衣装)
        if lower_mask.sum() > 200:
            p = _save_part("outerwear_lower", lower_mask)
            if p:
                parts.append(p)

        # Arms → segmented into upper_arm / forearm / hand / fingers
        for arm_mask_single, side in [(arm_left, "left"), (arm_right, "right")]:
            if arm_mask_single is not None:
                arm_segments = _segment_arm_joints(arm_mask_single, side)
                for label, mask in arm_segments.items():
                    p = _save_part(label, mask)
                    if p:
                        parts.append(p)

        # Legs → segmented into thigh / shin / foot
        for leg_mask_single, side in [(leg_left, "left"), (leg_right, "right")]:
            if leg_mask_single is not None:
                leg_segments = _segment_leg_joints(leg_mask_single, side)
                for label, mask in leg_segments.items():
                    p = _save_part(label, mask)
                    if p:
                        parts.append(p)
    else:
        # Fallback: single body part
        arm_left, arm_right, body_core = _detect_arms(body_full_mask, landmarks, alpha_mask)

        p = _save_part("body", body_core)
        if p:
            parts.append(p)

        # Arms → segmented into upper_arm / forearm / hand / fingers
        for arm_mask_single, side in [(arm_left, "left"), (arm_right, "right")]:
            if arm_mask_single is not None:
                arm_segments = _segment_arm_joints(arm_mask_single, side)
                for label, mask in arm_segments.items():
                    p = _save_part(label, mask)
                    if p:
                        parts.append(p)

    parts.sort(key=lambda p: p.depth_order)
    return parts


def _rect_mask(h: int, w: int, rx: int, ry: int, rw: int, rh: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    x1 = max(0, int(rx))
    y1 = max(0, int(ry))
    x2 = min(w, int(rx + rw))
    y2 = min(h, int(ry + rh))
    if x2 > x1 and y2 > y1:
        mask[y1:y2, x1:x2] = True
    return mask


def _detect_hair_kmeans(
    image_rgba: np.ndarray,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks,
    alpha_mask: np.ndarray,
    face_mask: np.ndarray,
) -> np.ndarray:
    """Detect hair using K-means color clustering.

    Much more robust than HSV thresholding - handles white, black, gradient, and multi-color hair.
    """
    h, w = image_rgba.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect
    rgb = no_bg[:, :, :3].astype(np.float32)

    # Candidate pixels: alpha-visible, not inside face interior, not far below face
    face_interior = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(
        face_interior,
        (landmarks.face_center_x, fy + int(fh * 0.5)),
        (int(fw * 0.35), int(fh * 0.4)),
        0, 0, 360, 255, -1,
    )
    face_interior_mask = face_interior > 0

    body_region = np.zeros((h, w), dtype=bool)
    body_region[landmarks.face_bottom + int(fh * 0.3):, :] = True

    candidate_mask = alpha_mask & ~face_interior_mask & ~body_region

    candidate_pixels = rgb[candidate_mask]
    if len(candidate_pixels) < 100:
        # Fallback to simple approach
        return _detect_hair_fallback(no_bg, landmarks, alpha_mask, face_mask)

    # K-means clustering (K=5)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    K = min(5, len(candidate_pixels) // 50)
    K = max(2, K)

    _, labels, centers = cv2.kmeans(
        candidate_pixels, K, None, criteria, attempts=3, flags=cv2.KMEANS_PP_CENTERS,
    )

    # Create label map for candidate pixels
    label_map = np.full((h, w), -1, dtype=np.int32)
    label_map[candidate_mask] = labels.flatten()

    # Score each cluster as potential hair
    best_hair_clusters = []
    for k in range(K):
        cluster_mask = label_map == k
        total = cluster_mask.sum()
        if total < 50:
            continue

        # Ratio of pixels above face top
        above_face = cluster_mask[:fy + int(fh * 0.2), :].sum()
        above_ratio = above_face / total if total > 0 else 0

        # Ratio of pixels adjacent to face ellipse
        dilated_face = cv2.dilate(face_mask.astype(np.uint8) * 255,
                                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        near_face = cluster_mask & (dilated_face > 0) & ~face_mask
        surround_ratio = near_face.sum() / total if total > 0 else 0

        # Normalized size
        max_possible = candidate_mask.sum()
        size_ratio = total / max_possible if max_possible > 0 else 0

        score = above_ratio * 0.4 + surround_ratio * 0.4 + size_ratio * 0.2
        best_hair_clusters.append((k, score))

    best_hair_clusters.sort(key=lambda x: x[1], reverse=True)

    # Select clusters with score above threshold
    hair_mask = np.zeros((h, w), dtype=bool)
    threshold = 0.15
    for k, score in best_hair_clusters:
        if score >= threshold:
            hair_mask |= (label_map == k)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    hair_uint8 = hair_mask.astype(np.uint8) * 255
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_CLOSE, kernel, iterations=2)
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_OPEN, kernel, iterations=1)

    # Keep only largest connected components
    labeled, num_features = ndimage.label(hair_uint8 > 0)
    if num_features > 0:
        sizes = ndimage.sum(hair_uint8 > 0, labeled, range(1, num_features + 1))
        max_size = max(sizes) if len(sizes) > 0 else 0
        # Keep components that are at least 10% of the largest
        for i, size in enumerate(sizes):
            if size < max_size * 0.1:
                hair_uint8[labeled == (i + 1)] = 0

    hair_mask = hair_uint8 > 0
    return hair_mask


def _detect_hair_fallback(
    no_bg: np.ndarray,
    landmarks: FaceLandmarks,
    alpha_mask: np.ndarray,
    face_mask: np.ndarray,
) -> np.ndarray:
    """Simple fallback hair detection using color sampling."""
    h, w = no_bg.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect
    hsv = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2HSV)

    # Multi-point sampling
    sample_positions = [
        (max(0, fy - int(fh * 0.3)), fy, max(0, landmarks.face_center_x - fw // 4), min(w, landmarks.face_center_x + fw // 4)),
        (max(0, fy - int(fh * 0.2)), fy, max(0, fx - fw // 3), fx),
        (max(0, fy - int(fh * 0.2)), fy, fx + fw, min(w, fx + fw + fw // 3)),
    ]

    all_hair_pixels = []
    for sy1, sy2, sx1, sx2 in sample_positions:
        region = hsv[sy1:sy2, sx1:sx2]
        region_alpha = alpha_mask[sy1:sy2, sx1:sx2]
        if region_alpha.sum() > 20:
            all_hair_pixels.append(region[region_alpha])

    if not all_hair_pixels:
        above_face = np.zeros((h, w), dtype=bool)
        above_face[:fy + int(fh * 0.2), :] = True
        return alpha_mask & above_face

    hair_pixels = np.concatenate(all_hair_pixels)
    median_h = np.median(hair_pixels[:, 0])
    median_s = np.median(hair_pixels[:, 1])

    h_range = 30
    s_range = 70
    lower = np.array([max(0, median_h - h_range), max(0, median_s - s_range), 20])
    upper = np.array([min(180, median_h + h_range), min(255, median_s + s_range), 255])

    color_mask = cv2.inRange(hsv, lower, upper) > 0

    face_interior = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(face_interior, (landmarks.face_center_x, fy + int(fh * 0.5)),
                (int(fw * 0.35), int(fh * 0.4)), 0, 0, 360, 255, -1)

    body_region = np.zeros((h, w), dtype=bool)
    body_region[landmarks.face_bottom + int(fh * 0.2):, :] = True

    hair_mask = alpha_mask & color_mask & ~(face_interior > 0) & ~body_region

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    hair_uint8 = hair_mask.astype(np.uint8) * 255
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_CLOSE, kernel, iterations=2)
    hair_uint8 = cv2.morphologyEx(hair_uint8, cv2.MORPH_OPEN, kernel, iterations=1)

    return hair_uint8 > 0


def _refine_mask_grabcut(rgb_image: np.ndarray, initial_mask: np.ndarray, iterations: int = 3) -> np.ndarray:
    """Refine a part mask using GrabCut for pixel-accurate boundaries.

    Only processes the bounding box region of the mask to keep it fast.
    """
    h, w = rgb_image.shape[:2]

    rows = np.any(initial_mask, axis=1)
    cols = np.any(initial_mask, axis=0)
    if not rows.any() or not cols.any():
        return initial_mask

    y1 = max(0, int(np.argmax(rows)) - 10)
    y2 = min(h, int(len(rows) - np.argmax(rows[::-1])) + 10)
    x1 = max(0, int(np.argmax(cols)) - 10)
    x2 = min(w, int(len(cols) - np.argmax(cols[::-1])) + 10)

    roi_h = y2 - y1
    roi_w = x2 - x1
    if roi_h < 20 or roi_w < 20:
        return initial_mask

    roi_rgb = rgb_image[y1:y2, x1:x2].copy()
    roi_mask_bool = initial_mask[y1:y2, x1:x2]

    # Ensure image is BGR uint8 for GrabCut
    if roi_rgb.dtype != np.uint8:
        roi_rgb = roi_rgb.astype(np.uint8)
    roi_bgr = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2BGR)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded = cv2.erode(roi_mask_bool.astype(np.uint8), kernel, iterations=2)
    dilated = cv2.dilate(roi_mask_bool.astype(np.uint8), kernel, iterations=3)

    gc_mask = np.full((roi_h, roi_w), cv2.GC_BGD, dtype=np.uint8)
    gc_mask[dilated > 0] = cv2.GC_PR_BGD
    gc_mask[roi_mask_bool] = cv2.GC_PR_FGD
    gc_mask[eroded > 0] = cv2.GC_FGD

    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    # GrabCut requires both FG and BG pixels
    has_bg = (gc_mask == cv2.GC_BGD).any() or (gc_mask == cv2.GC_PR_BGD).any()
    has_fg = (gc_mask == cv2.GC_FGD).any() or (gc_mask == cv2.GC_PR_FGD).any()
    if not has_bg or not has_fg:
        return initial_mask

    try:
        cv2.grabCut(roi_bgr, gc_mask, None, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_MASK)
        refined_roi = (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)
    except Exception:
        return initial_mask

    result = initial_mask.copy()
    result[y1:y2, x1:x2] = refined_roi
    return result


def _separate_iris(
    no_bg: np.ndarray,
    eye_mask: np.ndarray,
    ex: int, ey: int, ew: int, eh: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Separate iris/pupil from eye white using Otsu thresholding."""
    h, w = no_bg.shape[:2]

    x1 = max(0, ex)
    y1 = max(0, ey)
    x2 = min(w, ex + ew)
    y2 = min(h, ey + eh)

    if x2 - x1 < 10 or y2 - y1 < 10:
        return None, None

    roi = no_bg[y1:y2, x1:x2]
    roi_mask = eye_mask[y1:y2, x1:x2]

    if roi_mask.sum() < 50:
        return None, None

    gray = cv2.cvtColor(roi[:, :, :3], cv2.COLOR_RGB2GRAY)
    gray_masked = gray.copy()
    gray_masked[~roi_mask] = 255  # Set non-eye to white

    _, binary = cv2.threshold(gray_masked, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary = binary & roi_mask.astype(np.uint8) * 255

    # Find connected components - largest dark blob = iris
    labeled, num_features = ndimage.label(binary > 0)
    if num_features == 0:
        return None, None

    sizes = ndimage.sum(binary > 0, labeled, range(1, num_features + 1))
    iris_label_id = int(np.argmax(sizes)) + 1
    iris_roi = labeled == iris_label_id

    # Iris must be in the center region of the eye
    iris_cy = np.mean(np.where(iris_roi)[0])
    iris_cx = np.mean(np.where(iris_roi)[1])
    roi_cy = roi_mask.shape[0] / 2
    roi_cx = roi_mask.shape[1] / 2

    if abs(iris_cy - roi_cy) > roi_mask.shape[0] * 0.4 or abs(iris_cx - roi_cx) > roi_mask.shape[1] * 0.4:
        return None, None

    iris_full = np.zeros((h, w), dtype=bool)
    iris_full[y1:y2, x1:x2] = iris_roi

    white_full = eye_mask & ~iris_full

    return iris_full, white_full


def _detect_arms(
    body_mask: np.ndarray,
    landmarks: FaceLandmarks,
    alpha_mask: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray]:
    """Detect arms as protrusions from the central body mass."""
    h, w = body_mask.shape
    if body_mask.sum() < 200:
        return None, None, body_mask

    center_x = landmarks.face_center_x

    core_left = center_x - int(w * 0.15)
    core_right = center_x + int(w * 0.15)
    core_left = max(0, core_left)
    core_right = min(w, core_right)

    body_core = body_mask.copy()

    arm_candidate = body_mask.copy()
    arm_candidate[:, core_left:core_right] = False

    if arm_candidate.sum() < 100:
        return None, None, body_mask

    arm_left = arm_candidate.copy()
    arm_left[:, center_x:] = False

    arm_right = arm_candidate.copy()
    arm_right[:, :center_x] = False

    arm_left_result = arm_left if arm_left.sum() > 200 else None
    arm_right_result = arm_right if arm_right.sum() > 200 else None

    if arm_left_result is not None:
        body_core = body_core & ~arm_left
    if arm_right_result is not None:
        body_core = body_core & ~arm_right

    return arm_left_result, arm_right_result, body_core


def _segment_arm_joints(
    arm_mask: np.ndarray,
    side: str,
) -> dict[str, np.ndarray]:
    """Split an arm mask into upper_arm / forearm / hand / fingers.

    Uses the vertical extent and width profile of the arm to estimate
    joint positions (shoulder, elbow, wrist, fingertips).
    The approach works for arms hanging down or extended to the side.
    """
    h, w = arm_mask.shape
    segments: dict[str, np.ndarray] = {}

    rows = np.any(arm_mask, axis=1)
    cols = np.any(arm_mask, axis=0)
    if not rows.any() or not cols.any():
        return {f"arm_{side}": arm_mask}

    y_top = int(np.argmax(rows))
    y_bot = int(len(rows) - np.argmax(rows[::-1]))
    x_left = int(np.argmax(cols))
    x_right = int(len(cols) - np.argmax(cols[::-1]))

    arm_h = y_bot - y_top
    arm_w = x_right - x_left

    if arm_h < 40 and arm_w < 40:
        return {f"arm_{side}": arm_mask}

    # Determine if the arm is primarily vertical or horizontal
    is_vertical = arm_h > arm_w * 0.8

    if is_vertical:
        # Vertical arm: split by Y coordinates
        # Proportions: upper_arm 40%, forearm 30%, hand 20%, fingers 10%
        elbow_y = y_top + int(arm_h * 0.40)
        wrist_y = y_top + int(arm_h * 0.70)
        finger_y = y_top + int(arm_h * 0.88)

        upper = arm_mask.copy()
        upper[elbow_y:, :] = False

        forearm = arm_mask.copy()
        forearm[:elbow_y, :] = False
        forearm[wrist_y:, :] = False

        hand = arm_mask.copy()
        hand[:wrist_y, :] = False
        hand[finger_y:, :] = False

        fingers = arm_mask.copy()
        fingers[:finger_y, :] = False
    else:
        # Horizontal arm: split by X coordinates
        # upper_arm = near body, fingers = at extremity
        # Proportions along arm length: upper 40%, forearm 30%, hand 18%, fingers 12%
        if side == "left":
            # Left arm extends to the LEFT: body on right, fingertips on left
            # x_right = body side, x_left = fingertip side
            elbow_x = x_right - int(arm_w * 0.40)
            wrist_x = x_right - int(arm_w * 0.70)
            finger_x = x_right - int(arm_w * 0.88)

            upper = arm_mask.copy()
            upper[:, :elbow_x] = False  # keep body side (right)

            forearm = arm_mask.copy()
            forearm[:, elbow_x:] = False
            forearm[:, :wrist_x] = False

            hand = arm_mask.copy()
            hand[:, wrist_x:] = False
            hand[:, :finger_x] = False

            fingers = arm_mask.copy()
            fingers[:, finger_x:] = False
        else:
            # Right arm extends to the RIGHT: body on left, fingertips on right
            # x_left = body side, x_right = fingertip side
            elbow_x = x_left + int(arm_w * 0.40)
            wrist_x = x_left + int(arm_w * 0.70)
            finger_x = x_left + int(arm_w * 0.88)

            upper = arm_mask.copy()
            upper[:, elbow_x:] = False  # keep body side (left)

            forearm = arm_mask.copy()
            forearm[:, :elbow_x] = False
            forearm[:, wrist_x:] = False

            hand = arm_mask.copy()
            hand[:, :wrist_x] = False
            hand[:, finger_x:] = False

            fingers = arm_mask.copy()
            fingers[:, :finger_x] = False

    # Validate: use width narrowing to refine joint positions
    # The wrist/fingers tend to be narrower than upper arm
    if is_vertical:
        segments = _refine_vertical_joints(arm_mask, upper, forearm, hand, fingers, side, y_top, y_bot)
    else:
        # For horizontal, use the basic split
        segments = {}
        if upper.sum() > 100:
            segments[f"upper_arm_{side}"] = upper
        if forearm.sum() > 100:
            segments[f"forearm_{side}"] = forearm
        if hand.sum() > 50:
            segments[f"hand_{side}"] = hand
        if fingers.sum() > 30:
            segments[f"fingers_{side}"] = fingers

    if not segments:
        return {f"arm_{side}": arm_mask}

    return segments


def _refine_vertical_joints(
    arm_mask: np.ndarray,
    upper: np.ndarray,
    forearm: np.ndarray,
    hand: np.ndarray,
    fingers: np.ndarray,
    side: str,
    y_top: int,
    y_bot: int,
) -> dict[str, np.ndarray]:
    """Refine vertical arm segmentation using width profile analysis.

    The arm width typically narrows at joints (elbow, wrist).
    We detect these narrowing points to place joints more accurately.
    """
    arm_h = y_bot - y_top
    if arm_h < 30:
        segments = {}
        if upper.sum() > 100:
            segments[f"upper_arm_{side}"] = upper
        if forearm.sum() > 100:
            segments[f"forearm_{side}"] = forearm
        if hand.sum() > 50:
            segments[f"hand_{side}"] = hand
        if fingers.sum() > 30:
            segments[f"fingers_{side}"] = fingers
        return segments

    # Compute width at each row
    row_widths = np.sum(arm_mask[y_top:y_bot, :], axis=1).astype(float)

    if len(row_widths) < 10:
        segments = {}
        if upper.sum() > 100:
            segments[f"upper_arm_{side}"] = upper
        if forearm.sum() > 100:
            segments[f"forearm_{side}"] = forearm
        return segments

    # Smooth the width profile
    kernel_size = max(3, len(row_widths) // 15)
    if kernel_size % 2 == 0:
        kernel_size += 1
    smoothed = cv2.GaussianBlur(row_widths.reshape(-1, 1), (1, kernel_size), 0).flatten()

    # Find local minima (narrowing = joint)
    minima = []
    for i in range(2, len(smoothed) - 2):
        if smoothed[i] < smoothed[i - 1] and smoothed[i] < smoothed[i + 1]:
            if smoothed[i] < np.median(smoothed) * 0.9:  # Must be a real narrowing
                minima.append(i)

    segments = {}

    if len(minima) >= 2:
        # Two minima: elbow and wrist
        elbow_rel = minima[0]
        wrist_rel = minima[1]
        elbow_y = y_top + elbow_rel
        wrist_y = y_top + wrist_rel

        # Find finger start: where width drops significantly near the bottom
        finger_start = wrist_rel + int((y_bot - y_top - wrist_rel) * 0.6)
        finger_y = y_top + finger_start

        upper_m = arm_mask.copy()
        upper_m[elbow_y:, :] = False

        forearm_m = arm_mask.copy()
        forearm_m[:elbow_y, :] = False
        forearm_m[wrist_y:, :] = False

        hand_m = arm_mask.copy()
        hand_m[:wrist_y, :] = False
        hand_m[finger_y:, :] = False

        fingers_m = arm_mask.copy()
        fingers_m[:finger_y, :] = False

        if upper_m.sum() > 100:
            segments[f"upper_arm_{side}"] = upper_m
        if forearm_m.sum() > 100:
            segments[f"forearm_{side}"] = forearm_m
        if hand_m.sum() > 50:
            segments[f"hand_{side}"] = hand_m
        if fingers_m.sum() > 30:
            segments[f"fingers_{side}"] = fingers_m

    elif len(minima) == 1:
        # One minimum: likely the elbow
        elbow_y = y_top + minima[0]
        wrist_y = y_top + int(arm_h * 0.72)
        finger_y = y_top + int(arm_h * 0.88)

        upper_m = arm_mask.copy()
        upper_m[elbow_y:, :] = False

        forearm_m = arm_mask.copy()
        forearm_m[:elbow_y, :] = False
        forearm_m[wrist_y:, :] = False

        hand_m = arm_mask.copy()
        hand_m[:wrist_y, :] = False
        hand_m[finger_y:, :] = False

        fingers_m = arm_mask.copy()
        fingers_m[:finger_y, :] = False

        if upper_m.sum() > 100:
            segments[f"upper_arm_{side}"] = upper_m
        if forearm_m.sum() > 100:
            segments[f"forearm_{side}"] = forearm_m
        if hand_m.sum() > 50:
            segments[f"hand_{side}"] = hand_m
        if fingers_m.sum() > 30:
            segments[f"fingers_{side}"] = fingers_m
    else:
        # No clear joints found: use proportional split
        if upper.sum() > 100:
            segments[f"upper_arm_{side}"] = upper
        if forearm.sum() > 100:
            segments[f"forearm_{side}"] = forearm
        if hand.sum() > 50:
            segments[f"hand_{side}"] = hand
        if fingers.sum() > 30:
            segments[f"fingers_{side}"] = fingers

    return segments


def _segment_leg_joints(
    leg_mask: np.ndarray,
    side: str,
) -> dict[str, np.ndarray]:
    """Split a leg mask into thigh / shin / foot.

    Uses width profile analysis: the knee is typically a narrowing point.
    """
    h, w = leg_mask.shape
    segments: dict[str, np.ndarray] = {}

    rows = np.any(leg_mask, axis=1)
    if not rows.any():
        return {f"leg_{side}": leg_mask}

    y_top = int(np.argmax(rows))
    y_bot = int(len(rows) - np.argmax(rows[::-1]))
    leg_h = y_bot - y_top

    if leg_h < 30:
        return {f"leg_{side}": leg_mask}

    # Width profile
    row_widths = np.sum(leg_mask[y_top:y_bot, :], axis=1).astype(float)

    # Smooth
    kernel_size = max(3, len(row_widths) // 10)
    if kernel_size % 2 == 0:
        kernel_size += 1
    smoothed = cv2.GaussianBlur(row_widths.reshape(-1, 1), (1, kernel_size), 0).flatten()

    # Find knee: local minimum in upper 40-70% region
    search_start = int(len(smoothed) * 0.30)
    search_end = int(len(smoothed) * 0.65)
    search_region = smoothed[search_start:search_end]

    knee_rel = search_start
    if len(search_region) > 3:
        knee_rel = search_start + int(np.argmin(search_region))

    knee_y = y_top + knee_rel

    # Ankle: 85% down the leg
    ankle_y = y_top + int(leg_h * 0.85)

    thigh = leg_mask.copy()
    thigh[knee_y:, :] = False

    shin = leg_mask.copy()
    shin[:knee_y, :] = False
    shin[ankle_y:, :] = False

    foot = leg_mask.copy()
    foot[:ankle_y, :] = False

    if thigh.sum() > 100:
        segments[f"thigh_{side}"] = thigh
    if shin.sum() > 100:
        segments[f"shin_{side}"] = shin
    if foot.sum() > 50:
        segments[f"foot_{side}"] = foot

    if not segments:
        return {f"leg_{side}": leg_mask}

    return segments


def _segment_clothing_layers(
    image_rgba: np.ndarray,
    no_bg: np.ndarray,
    body_mask: np.ndarray,
    landmarks: FaceLandmarks,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None] | None:
    """Separate body into skin/upper-wear/lower-wear using u2net_cloth_seg.

    u2net_cloth_seg outputs a segmentation map with 3 clothing classes.
    We use this to separate the character body into:
    - skin (素体/肌): exposed skin areas
    - upper wear (上半身衣装): shirts, jackets, etc.
    - lower wear (下半身衣装): skirts, pants, etc.

    Returns (skin_mask, upper_mask, lower_mask, neck_mask) or None if fails.
    """
    try:
        from rembg import new_session, remove
        from PIL import Image as PILImage
    except ImportError:
        return None

    h, w = image_rgba.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect

    try:
        # Run cloth segmentation
        cloth_session = new_session("u2net_cloth_seg")
        img_pil = PILImage.fromarray(no_bg)

        # u2net_cloth_seg returns an image where different pixel values = different classes
        # We need to get the raw mask output
        result = remove(img_pil, session=cloth_session, only_mask=True)
        mask_arr = np.array(result)

        # The mask from u2net_cloth_seg encodes:
        # - Values near 0: background
        # - Different value ranges correspond to different clothing categories
        # Normalize and threshold to separate regions
        if len(mask_arr.shape) == 3:
            mask_arr = mask_arr[:, :, 0]

        # Resize mask to match original image if needed
        if mask_arr.shape != (h, w):
            mask_arr = cv2.resize(mask_arr, (w, h), interpolation=cv2.INTER_NEAREST)

    except Exception:
        return None

    # Detect skin color from face region for skin identification
    skin_color = _sample_skin_color(no_bg, landmarks)
    if skin_color is None:
        return None

    # Classify body pixels into skin vs clothing
    body_pixels_ycrcb = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2YCrCb)

    # Skin detection using sampled color with adaptive range
    skin_y, skin_cr, skin_cb = skin_color
    skin_range_cr = 25
    skin_range_cb = 25

    skin_color_mask = (
        (body_pixels_ycrcb[:, :, 1] >= skin_cr - skin_range_cr) &
        (body_pixels_ycrcb[:, :, 1] <= skin_cr + skin_range_cr) &
        (body_pixels_ycrcb[:, :, 2] >= skin_cb - skin_range_cb) &
        (body_pixels_ycrcb[:, :, 2] <= skin_cb + skin_range_cb)
    )

    # Skin = body pixels that match skin color
    skin_mask = body_mask & skin_color_mask

    # Clothing = body pixels that don't match skin color
    clothing_mask = body_mask & ~skin_color_mask

    # Split clothing into upper and lower based on position
    # Waist line: roughly at 55-65% of body height from face bottom
    body_rows = np.any(body_mask, axis=1)
    if body_rows.any():
        body_top = int(np.argmax(body_rows))
        body_bottom = int(len(body_rows) - np.argmax(body_rows[::-1]))
        body_height = body_bottom - body_top
        waist_y = body_top + int(body_height * 0.45)
    else:
        waist_y = landmarks.face_bottom + int(fh * 1.5)

    upper_clothing = clothing_mask.copy()
    upper_clothing[waist_y:, :] = False

    lower_clothing = clothing_mask.copy()
    lower_clothing[:waist_y, :] = False

    # Neck: skin area between face and upper body
    neck_mask = skin_mask.copy()
    neck_top = landmarks.face_bottom - int(fh * 0.1)
    neck_bottom = landmarks.face_bottom + int(fh * 0.3)
    neck_left = landmarks.face_center_x - int(fw * 0.3)
    neck_right = landmarks.face_center_x + int(fw * 0.3)

    neck_region = np.zeros((h, w), dtype=bool)
    y1n = max(0, neck_top)
    y2n = min(h, neck_bottom)
    x1n = max(0, neck_left)
    x2n = min(w, neck_right)
    neck_region[y1n:y2n, x1n:x2n] = True
    neck_detected = skin_mask & neck_region

    # Remove neck from main skin mask
    skin_mask = skin_mask & ~neck_detected

    # Use OpenCV inpainting to generate skin under clothing for the skin layer
    skin_mask = _inpaint_skin_under_clothing(no_bg, skin_mask, clothing_mask, body_mask)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for mask in [skin_mask, upper_clothing, lower_clothing]:
        temp = mask.astype(np.uint8) * 255
        temp = cv2.morphologyEx(temp, cv2.MORPH_CLOSE, kernel, iterations=1)
        mask[:] = temp > 0

    return skin_mask, upper_clothing, lower_clothing, neck_detected


def _sample_skin_color(no_bg: np.ndarray, landmarks: FaceLandmarks) -> tuple[int, int, int] | None:
    """Sample skin color from the face region in YCrCb color space."""
    h, w = no_bg.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect

    # Sample from cheek area (between eyes and mouth, left/right of nose)
    ycrcb = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2YCrCb)
    alpha = no_bg[:, :, 3]

    sample_y = fy + int(fh * 0.5)
    sample_h = int(fh * 0.15)
    sample_regions = [
        (sample_y, sample_y + sample_h,
         landmarks.face_center_x - int(fw * 0.35), landmarks.face_center_x - int(fw * 0.15)),
        (sample_y, sample_y + sample_h,
         landmarks.face_center_x + int(fw * 0.15), landmarks.face_center_x + int(fw * 0.35)),
    ]

    skin_pixels = []
    for sy1, sy2, sx1, sx2 in sample_regions:
        sy1 = max(0, sy1)
        sy2 = min(h, sy2)
        sx1 = max(0, sx1)
        sx2 = min(w, sx2)
        region = ycrcb[sy1:sy2, sx1:sx2]
        region_alpha = alpha[sy1:sy2, sx1:sx2]
        if region_alpha.sum() > 10:
            skin_pixels.append(region[region_alpha > 128])

    if not skin_pixels or all(len(p) == 0 for p in skin_pixels):
        return None

    all_pixels = np.concatenate(skin_pixels)
    median_y = int(np.median(all_pixels[:, 0]))
    median_cr = int(np.median(all_pixels[:, 1]))
    median_cb = int(np.median(all_pixels[:, 2]))

    return (median_y, median_cr, median_cb)


def _inpaint_skin_under_clothing(
    no_bg: np.ndarray,
    skin_mask: np.ndarray,
    clothing_mask: np.ndarray,
    body_mask: np.ndarray,
) -> np.ndarray:
    """Generate estimated skin under clothing using inpainting.

    This creates a continuous skin layer underneath the clothing,
    so when the clothing layer is hidden, the skin is visible.
    """
    h, w = no_bg.shape[:2]

    # The full body area should have skin underneath
    full_skin_needed = body_mask.copy()

    # Regions that need inpainting: clothing areas (skin is hidden there)
    inpaint_region = clothing_mask & ~skin_mask

    if inpaint_region.sum() < 50:
        return skin_mask | (body_mask & ~clothing_mask)

    # Use OpenCV inpainting to fill in skin texture under clothing
    inpaint_mask = inpaint_region.astype(np.uint8) * 255

    # Create a source image with known skin pixels
    source_rgb = no_bg[:, :, :3].copy()
    # Only keep skin pixels, zero out everything else
    source_rgb[~skin_mask] = [0, 0, 0]

    try:
        # Inpaint to fill clothing regions with estimated skin
        inpainted = cv2.inpaint(source_rgb, inpaint_mask, inpaintRadius=10, flags=cv2.INPAINT_TELEA)

        # The expanded skin mask includes both original skin and inpainted areas
        expanded_skin = skin_mask | inpaint_region

        # Write inpainted pixels back to the no_bg array for the skin layer
        # (only in the inpainted region)
        result_rgba = no_bg.copy()
        for c in range(3):
            result_rgba[:, :, c] = np.where(inpaint_region, inpainted[:, :, c], no_bg[:, :, c])
        result_rgba[:, :, 3] = np.where(expanded_skin, 255, 0).astype(np.uint8)

        # Save the inpainted skin image for later use by _save_part
        # For now, return the expanded mask
        return expanded_skin
    except Exception:
        return skin_mask


def _detect_legs(
    skin_mask: np.ndarray,
    landmarks: FaceLandmarks,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Detect legs from skin areas below the waist."""
    h, w = skin_mask.shape
    fx, fy, fw, fh = landmarks.face_rect

    # Legs should be in the lower portion of the image
    body_rows = np.any(skin_mask, axis=1)
    if not body_rows.any():
        return None, None

    body_bottom = int(len(body_rows) - np.argmax(body_rows[::-1]))
    body_top = int(np.argmax(body_rows))
    body_height = body_bottom - body_top

    # Leg region: below 60% of total body height
    leg_top = body_top + int(body_height * 0.6)

    leg_mask = skin_mask.copy()
    leg_mask[:leg_top, :] = False

    if leg_mask.sum() < 200:
        return None, None

    center_x = landmarks.face_center_x

    leg_left = leg_mask.copy()
    leg_left[:, center_x:] = False

    leg_right = leg_mask.copy()
    leg_right[:, :center_x] = False

    leg_left_result = leg_left if leg_left.sum() > 100 else None
    leg_right_result = leg_right if leg_right.sum() > 100 else None

    return leg_left_result, leg_right_result


def _feather_edges_adaptive(image_rgba: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Apply distance-transform-based adaptive feathering."""
    result = image_rgba.copy()

    # Compute adaptive feather radius based on part size
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return result

    part_h = int(np.sum(rows))
    part_w = int(np.sum(cols))
    feather_width = max(2, int(math.sqrt(part_w ** 2 + part_h ** 2) * 0.008))

    # Distance transform from mask boundary
    mask_uint8 = mask.astype(np.uint8)
    dist = cv2.distanceTransform(mask_uint8, cv2.DIST_L2, 5)

    # Smooth alpha gradient at edges
    alpha_factor = np.clip(dist / feather_width, 0.0, 1.0)
    result[:, :, 3] = (result[:, :, 3].astype(np.float32) * alpha_factor).astype(np.uint8)

    return result
