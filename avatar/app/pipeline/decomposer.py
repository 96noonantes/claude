"""Main decomposition pipeline: combines background removal, face detection, and region segmentation.

Supports two modes:
- "full": Full character decomposition (face, hair, body, clothing, limbs)
- "costume_only": Extract only clothing/costume layers (upper, lower, accessories)
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.models.session import PartData, BodyProfile
from app.pipeline.preprocessing import load_and_normalize, remove_background
from app.pipeline.face_detector import detect_anime_face
from app.pipeline.region_segmenter import segment_parts
from app.pipeline.inpainter import inpaint_occluded_parts
from app.pipeline.gender_detector import detect_gender
from app.pipeline.costume_classifier import classify_costume_parts
from app.pipeline.body_analyzer import analyze_body, normalize_part_bounds, compute_anchor
from app.pipeline.fit_points import compute_fit_points
from app.pipeline.part_labels import get_label_ja, get_depth_order


def run_decomposition(
    image_path: Path,
    output_dir: Path,
    mode: str = "full",
) -> tuple[list[PartData], BodyProfile]:
    """Run decomposition pipeline.

    Returns (parts, body_profile).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    image_rgba = load_and_normalize(image_path)
    no_bg = remove_background(image_rgba)

    landmarks = detect_anime_face(no_bg)

    if mode == "costume_only":
        parts = _run_costume_only(image_rgba, no_bg, output_dir)
    else:
        parts = _run_full(image_rgba, no_bg, output_dir, landmarks)

    # --- Post-processing: body profile + normalize + fit points ---
    body_profile = analyze_body(no_bg, landmarks, parts)

    # Make IDs stable (label-based instead of sequential)
    _assign_stable_ids(parts)

    # Classify gender & categories (for both modes)
    gender_result = detect_gender(no_bg, landmarks)
    parts = classify_costume_parts(parts, gender_result, no_bg, landmarks, output_dir)

    # Normalize coordinates and compute fit points
    for part in parts:
        part.normalized_bounds = normalize_part_bounds(part, body_profile)
        part.anchor = compute_anchor(part, body_profile)
        part.fit_points = compute_fit_points(part, body_profile)

    return parts, body_profile


def _assign_stable_ids(parts: list[PartData]) -> None:
    """Assign stable IDs based on label. Handles duplicate labels with suffix."""
    seen: dict[str, int] = {}
    for part in parts:
        label = part.label
        if label in seen:
            seen[label] += 1
            part.id = f"{label}_{seen[label]}"
        else:
            seen[label] = 0
            part.id = label


def _run_full(
    image_rgba: np.ndarray,
    no_bg: np.ndarray,
    output_dir: Path,
    landmarks=None,
) -> list[PartData]:
    """Full decomposition: face, hair, body, clothing, limbs."""
    if landmarks is None:
        raise ValueError(
            "キャラクターの顔を検出できませんでした。"
            "正面を向いたアニメキャラクターの画像を使用してください。"
        )

    parts = segment_parts(image_rgba, no_bg, landmarks, output_dir)
    if not parts:
        raise ValueError("パーツの分解に失敗しました。画像を確認してください。")

    # Post-process: inpaint occluded regions so each part is complete
    parts = inpaint_occluded_parts(no_bg, parts, output_dir)

    return parts


def _run_costume_only(image_rgba: np.ndarray, no_bg: np.ndarray, output_dir: Path) -> list[PartData]:
    """Costume-only extraction: separate clothing from the character.

    Uses skin color detection to identify clothing vs skin, then splits
    clothing into upper/lower/accessory categories.
    """
    h, w = no_bg.shape[:2]
    alpha_mask = no_bg[:, :, 3] > 128
    rgb = no_bg[:, :, :3]

    # Detect face for skin color sampling and body region identification
    landmarks = detect_anime_face(no_bg)

    parts: list[PartData] = []
    part_counter = 0

    def _save_part(label: str, mask: np.ndarray) -> PartData | None:
        nonlocal part_counter
        if mask.sum() < 100:
            return None

        masked = no_bg.copy()
        masked[~mask] = [0, 0, 0, 0]

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return None

        y1 = max(0, int(np.argmax(rows)) - 3)
        y2 = min(h, int(len(rows) - np.argmax(rows[::-1])) + 3)
        x1 = max(0, int(np.argmax(cols)) - 3)
        x2 = min(w, int(len(cols) - np.argmax(cols[::-1])) + 3)

        part_img = masked[y1:y2, x1:x2]
        filename = f"{label}.png"
        Image.fromarray(part_img).save(output_dir / filename)

        part_counter += 1
        return PartData(
            id=label,  # stable ID = label (deduplicated by _assign_stable_ids)
            label=label,
            label_ja=get_label_ja(label),
            bounds={"x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)},
            depth_order=get_depth_order(label),
            visible=True,
            image_filename=filename,
        )

    # --- Detect skin color ---
    skin_mask = _detect_skin(no_bg, landmarks, alpha_mask)

    # --- Clothing = character minus skin minus hair ---
    clothing_mask = alpha_mask & ~skin_mask

    # Remove hair region from clothing if face was detected
    if landmarks is not None:
        hair_mask = _estimate_hair_region(no_bg, landmarks, alpha_mask)
        clothing_mask = clothing_mask & ~hair_mask

    if clothing_mask.sum() < 200:
        raise ValueError("衣装を検出できませんでした。キャラクターが衣服を着ている画像を使用してください。")

    # --- Split clothing by vertical position ---
    char_rows = np.any(alpha_mask, axis=1)
    char_top = int(np.argmax(char_rows))
    char_bottom = int(len(char_rows) - np.argmax(char_rows[::-1]))
    char_height = char_bottom - char_top

    # Use face position if available, otherwise estimate
    if landmarks is not None:
        waist_y = landmarks.face_bottom + int(char_height * 0.25)
        chest_y = landmarks.face_bottom
    else:
        waist_y = char_top + int(char_height * 0.45)
        chest_y = char_top + int(char_height * 0.25)

    # --- Upper clothing (chest to waist) ---
    upper_clothing = clothing_mask.copy()
    upper_clothing[waist_y:, :] = False
    # Also remove face area
    if landmarks is not None:
        upper_clothing[:landmarks.face_top, :] = False

    # --- Lower clothing (waist to feet) ---
    lower_clothing = clothing_mask.copy()
    lower_clothing[:waist_y, :] = False

    # --- Try to further separate lower clothing into skirt/pants vs socks/shoes ---
    knee_y = waist_y + int((char_bottom - waist_y) * 0.5)
    ankle_y = waist_y + int((char_bottom - waist_y) * 0.85)

    skirt_pants = lower_clothing.copy()
    skirt_pants[knee_y:, :] = False

    legwear = lower_clothing.copy()
    legwear[:knee_y, :] = False
    legwear[ankle_y:, :] = False

    footwear = lower_clothing.copy()
    footwear[:ankle_y, :] = False

    # --- Collar / neckwear (around neck area) ---
    if landmarks is not None:
        collar_region = clothing_mask.copy()
        collar_top = landmarks.face_bottom - int(char_height * 0.02)
        collar_bottom = landmarks.face_bottom + int(char_height * 0.06)
        collar_region[:collar_top, :] = False
        collar_region[collar_bottom:, :] = False
        center_x = landmarks.face_center_x
        collar_left = center_x - int(w * 0.2)
        collar_right = center_x + int(w * 0.2)
        collar_region[:, :max(0, collar_left)] = False
        collar_region[:, min(w, collar_right):] = False

        p = _save_part("collar", collar_region)
        if p:
            parts.append(p)

        # Remove collar from upper clothing to avoid overlap
        upper_clothing = upper_clothing & ~collar_region

    # --- Detect sleeves (clothing on arms) ---
    if landmarks is not None:
        center_x = landmarks.face_center_x
        arm_region = clothing_mask.copy()
        # Arms are outside the body core
        core_left = center_x - int(w * 0.12)
        core_right = center_x + int(w * 0.12)
        arm_region[:, core_left:core_right] = False
        arm_region[:chest_y, :] = False
        arm_region[waist_y:, :] = False

        sleeve_left = arm_region.copy()
        sleeve_left[:, center_x:] = False
        p = _save_part("sleeve_left", sleeve_left)
        if p:
            parts.append(p)

        sleeve_right = arm_region.copy()
        sleeve_right[:, :center_x] = False
        p = _save_part("sleeve_right", sleeve_right)
        if p:
            parts.append(p)

        # Remove sleeves from upper clothing
        upper_clothing = upper_clothing & ~arm_region

    # --- Save clothing parts ---
    p = _save_part("outerwear_upper", upper_clothing)
    if p:
        parts.append(p)

    p = _save_part("outerwear_lower", skirt_pants)
    if p:
        parts.append(p)

    p = _save_part("legwear", legwear)
    if p:
        parts.append(p)

    p = _save_part("footwear", footwear)
    if p:
        parts.append(p)

    # --- Headwear: clothing above the face ---
    if landmarks is not None:
        headwear = clothing_mask.copy()
        headwear[landmarks.face_top:, :] = False
        p = _save_part("headwear", headwear)
        if p:
            parts.append(p)

    # --- Full costume composite (all clothing combined) ---
    p = _save_part("costume_full", clothing_mask)
    if p:
        parts.append(p)

    if not parts:
        raise ValueError("衣装パーツの抽出に失敗しました。")

    parts.sort(key=lambda p: p.depth_order)

    return parts


def _detect_skin(no_bg: np.ndarray, landmarks, alpha_mask: np.ndarray) -> np.ndarray:
    """Detect skin pixels using face color sampling + YCrCb range."""
    h, w = no_bg.shape[:2]
    ycrcb = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2YCrCb)

    if landmarks is not None:
        # Sample skin color from cheeks
        fx, fy, fw, fh = landmarks.face_rect
        sy = fy + int(fh * 0.45)
        sh = int(fh * 0.15)
        samples = []
        for sx1, sx2 in [
            (landmarks.face_center_x - int(fw * 0.35), landmarks.face_center_x - int(fw * 0.1)),
            (landmarks.face_center_x + int(fw * 0.1), landmarks.face_center_x + int(fw * 0.35)),
        ]:
            sx1 = max(0, sx1)
            sx2 = min(w, sx2)
            region = ycrcb[sy:sy + sh, sx1:sx2]
            region_alpha = alpha_mask[sy:sy + sh, sx1:sx2]
            if region_alpha.sum() > 10:
                samples.append(region[region_alpha])

        if samples:
            pixels = np.concatenate(samples)
            med_cr = int(np.median(pixels[:, 1]))
            med_cb = int(np.median(pixels[:, 2]))

            skin_mask = (
                (ycrcb[:, :, 1] >= med_cr - 20) & (ycrcb[:, :, 1] <= med_cr + 20) &
                (ycrcb[:, :, 2] >= med_cb - 20) & (ycrcb[:, :, 2] <= med_cb + 20) &
                alpha_mask
            )

            # Include face ellipse as definite skin
            face_ellipse = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(
                face_ellipse,
                (landmarks.face_center_x, fy + int(fh * 0.5)),
                (int(fw * 0.4), int(fh * 0.45)),
                0, 0, 360, 255, -1,
            )
            skin_mask = skin_mask | ((face_ellipse > 0) & alpha_mask)
            return skin_mask

    # Fallback: broad skin color range
    skin_mask = cv2.inRange(ycrcb, np.array([50, 130, 75]), np.array([255, 175, 130]))
    return (skin_mask > 0) & alpha_mask


def _estimate_hair_region(no_bg: np.ndarray, landmarks, alpha_mask: np.ndarray) -> np.ndarray:
    """Quick hair region estimate for costume-only mode."""
    h, w = no_bg.shape[:2]
    fx, fy, fw, fh = landmarks.face_rect
    hsv = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2HSV)

    # Sample hair color from above face
    sy1 = max(0, fy - int(fh * 0.3))
    sy2 = fy
    sx1 = max(0, landmarks.face_center_x - fw // 3)
    sx2 = min(w, landmarks.face_center_x + fw // 3)

    sample = hsv[sy1:sy2, sx1:sx2]
    sample_alpha = alpha_mask[sy1:sy2, sx1:sx2]

    if sample_alpha.sum() < 30:
        # No hair above face, return empty
        return np.zeros((h, w), dtype=bool)

    hair_pixels = sample[sample_alpha]
    med_h = np.median(hair_pixels[:, 0])
    med_s = np.median(hair_pixels[:, 1])

    lower = np.array([max(0, med_h - 30), max(0, med_s - 70), 20])
    upper = np.array([min(180, med_h + 30), min(255, med_s + 70), 255])
    color_mask = cv2.inRange(hsv, lower, upper) > 0

    # Hair is above + around the face
    face_interior = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(face_interior, (landmarks.face_center_x, fy + int(fh * 0.5)),
                (int(fw * 0.3), int(fh * 0.35)), 0, 0, 360, 255, -1)

    body_below = np.zeros((h, w), dtype=bool)
    body_below[landmarks.face_bottom + int(fh * 0.3):, :] = True

    hair_mask = alpha_mask & color_mask & ~(face_interior > 0) & ~body_below
    return hair_mask
