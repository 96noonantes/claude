"""Automatic gender detection from anime character image.

Uses multiple visual features (face shape, eye size, silhouette, clothing shape,
hair length) to estimate gender with a confidence score.
"""

import cv2
import numpy as np
from dataclasses import dataclass

from app.pipeline.face_detector import FaceLandmarks


@dataclass
class GenderResult:
    gender: str          # "male" or "female"
    confidence: float    # 0.0 to 1.0
    features: dict       # individual feature scores for debugging


def detect_gender(
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
) -> GenderResult:
    """Detect character gender from image features.

    Scoring: positive = female, negative = male. Normalized to [-1, 1].
    """
    h, w = no_bg.shape[:2]
    alpha_mask = no_bg[:, :, 3] > 128
    features = {}

    score = 0.0

    # --- Feature 1: Face aspect ratio (weight=0.15) ---
    if landmarks is not None:
        fx, fy, fw, fh = landmarks.face_rect
        face_aspect = fh / max(fw, 1)
        # Female: rounder face (aspect < 1.25), Male: longer face (aspect > 1.3)
        if face_aspect < 1.15:
            f1 = 0.8   # very round = female
        elif face_aspect < 1.25:
            f1 = 0.3
        elif face_aspect > 1.4:
            f1 = -0.8  # very long = male
        elif face_aspect > 1.3:
            f1 = -0.3
        else:
            f1 = 0.0
        features["face_aspect"] = f1
        score += f1 * 0.15

    # --- Feature 2: Eye size ratio (weight=0.2) ---
    if landmarks is not None:
        fx, fy, fw, fh = landmarks.face_rect
        lex, ley = landmarks.left_eye_center
        rex, rey = landmarks.right_eye_center
        lew = landmarks.left_eye_rect[2]
        leh = landmarks.left_eye_rect[3]
        rew = landmarks.right_eye_rect[2]
        reh = landmarks.right_eye_rect[3]

        avg_eye_area = (lew * leh + rew * reh) / 2
        face_area = fw * fh
        eye_ratio = avg_eye_area / max(face_area, 1)

        # Female anime: larger eyes relative to face
        if eye_ratio > 0.06:
            f2 = 0.8
        elif eye_ratio > 0.04:
            f2 = 0.3
        elif eye_ratio < 0.02:
            f2 = -0.7
        elif eye_ratio < 0.03:
            f2 = -0.3
        else:
            f2 = 0.0
        features["eye_size"] = f2
        score += f2 * 0.2

    # --- Feature 3: Skirt detection - strongest signal (weight=0.3) ---
    f3 = _detect_skirt_shape(no_bg, landmarks, alpha_mask)
    features["skirt_shape"] = f3
    score += f3 * 0.3

    # --- Feature 4: Waist narrowing / body silhouette (weight=0.15) ---
    f4 = _detect_waist_curve(alpha_mask, landmarks)
    features["waist_curve"] = f4
    score += f4 * 0.15

    # --- Feature 5: Hair length (weight=0.1) ---
    f5 = _detect_hair_length(no_bg, landmarks, alpha_mask)
    features["hair_length"] = f5
    score += f5 * 0.1

    # --- Feature 6: Shoulder width (weight=0.1) ---
    f6 = _detect_shoulder_width(alpha_mask, landmarks)
    features["shoulder_width"] = f6
    score += f6 * 0.1

    # Determine gender
    if score > 0.05:
        gender = "female"
        confidence = min(1.0, abs(score) * 2.5)
    elif score < -0.05:
        gender = "male"
        confidence = min(1.0, abs(score) * 2.5)
    else:
        gender = "female"  # default for anime
        confidence = 0.3

    return GenderResult(gender=gender, confidence=round(confidence, 2), features=features)


def _detect_skirt_shape(
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    alpha_mask: np.ndarray,
) -> float:
    """Detect if the lower body clothing flares out (skirt) or stays straight (pants).

    Returns: positive = skirt (female), negative = pants/straight (male/unisex)
    """
    h, w = alpha_mask.shape

    # Find the waist and knee regions
    rows = np.any(alpha_mask, axis=1)
    if not rows.any():
        return 0.0

    char_top = int(np.argmax(rows))
    char_bottom = int(len(rows) - np.argmax(rows[::-1]))
    char_height = char_bottom - char_top

    if landmarks is not None:
        waist_y = landmarks.face_bottom + int(char_height * 0.15)
    else:
        waist_y = char_top + int(char_height * 0.45)

    knee_y = waist_y + int(char_height * 0.25)
    knee_y = min(knee_y, char_bottom - 10)

    if knee_y <= waist_y + 10:
        return 0.0

    # Measure width at waist and at knee level
    waist_width = np.sum(alpha_mask[waist_y, :])
    knee_width = np.sum(alpha_mask[min(knee_y, h - 1), :])

    if waist_width < 10:
        return 0.0

    width_ratio = knee_width / max(waist_width, 1)

    # Width profile: measure how the width changes from waist to knee
    widths = []
    for y in range(waist_y, min(knee_y, h)):
        widths.append(np.sum(alpha_mask[y, :]))

    if len(widths) < 5:
        return 0.0

    widths = np.array(widths, dtype=float)
    # Smooth
    if len(widths) > 10:
        kernel = np.ones(5) / 5
        widths = np.convolve(widths, kernel, mode='same')

    # Check if width increases (flares out = skirt)
    first_quarter = np.mean(widths[:len(widths) // 4])
    last_quarter = np.mean(widths[3 * len(widths) // 4:])

    if first_quarter < 5:
        return 0.0

    flare_ratio = last_quarter / max(first_quarter, 1)

    if flare_ratio > 1.3:
        return 0.9   # clearly flaring = skirt
    elif flare_ratio > 1.1:
        return 0.4
    elif flare_ratio < 0.85:
        return -0.5  # narrowing = pants/legs
    else:
        return 0.0   # neutral


def _detect_waist_curve(
    alpha_mask: np.ndarray,
    landmarks: FaceLandmarks | None,
) -> float:
    """Detect waist narrowing (hourglass = female, straight = male)."""
    h, w = alpha_mask.shape

    rows = np.any(alpha_mask, axis=1)
    if not rows.any():
        return 0.0

    char_top = int(np.argmax(rows))
    char_bottom = int(len(rows) - np.argmax(rows[::-1]))
    char_height = char_bottom - char_top

    if landmarks is not None:
        chest_y = landmarks.face_bottom + int(char_height * 0.05)
        waist_y = landmarks.face_bottom + int(char_height * 0.15)
        hip_y = landmarks.face_bottom + int(char_height * 0.25)
    else:
        chest_y = char_top + int(char_height * 0.35)
        waist_y = char_top + int(char_height * 0.45)
        hip_y = char_top + int(char_height * 0.55)

    chest_w = np.sum(alpha_mask[min(chest_y, h - 1), :])
    waist_w = np.sum(alpha_mask[min(waist_y, h - 1), :])
    hip_w = np.sum(alpha_mask[min(hip_y, h - 1), :])

    if chest_w < 10 or hip_w < 10:
        return 0.0

    # Waist should be narrower than both chest and hip for female
    avg_wide = (chest_w + hip_w) / 2
    narrowing = 1.0 - (waist_w / max(avg_wide, 1))

    if narrowing > 0.15:
        return 0.7   # strong hourglass
    elif narrowing > 0.08:
        return 0.3
    elif narrowing < -0.05:
        return -0.4  # waist wider than average = male/bulky
    else:
        return 0.0


def _detect_hair_length(
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    alpha_mask: np.ndarray,
) -> float:
    """Detect hair length relative to body. Long hair = female tendency."""
    if landmarks is None:
        return 0.0

    h, w = alpha_mask.shape
    fx, fy, fw, fh = landmarks.face_rect

    # Estimate hair region (above + sides of face)
    hsv = cv2.cvtColor(no_bg[:, :, :3], cv2.COLOR_RGB2HSV)

    # Sample hair color from above face
    sy1 = max(0, fy - int(fh * 0.3))
    sy2 = fy
    sx1 = max(0, landmarks.face_center_x - fw // 3)
    sx2 = min(w, landmarks.face_center_x + fw // 3)

    sample = hsv[sy1:sy2, sx1:sx2]
    sample_alpha = alpha_mask[sy1:sy2, sx1:sx2]

    if sample_alpha.sum() < 20:
        return 0.0

    hair_pixels = sample[sample_alpha]
    med_h = np.median(hair_pixels[:, 0])
    med_s = np.median(hair_pixels[:, 1])

    lower = np.array([max(0, med_h - 30), max(0, med_s - 70), 20])
    upper = np.array([min(180, med_h + 30), min(255, med_s + 70), 255])
    hair_mask = cv2.inRange(hsv, lower, upper) > 0
    hair_mask = hair_mask & alpha_mask

    # Find how far down hair extends
    hair_rows = np.any(hair_mask, axis=1)
    if not hair_rows.any():
        return 0.0

    hair_bottom = int(len(hair_rows) - np.argmax(hair_rows[::-1]))
    hair_extent = hair_bottom - landmarks.face_bottom

    char_rows = np.any(alpha_mask, axis=1)
    char_bottom = int(len(char_rows) - np.argmax(char_rows[::-1]))
    body_height = char_bottom - landmarks.face_bottom

    if body_height < 10:
        return 0.0

    hair_ratio = hair_extent / body_height

    if hair_ratio > 0.6:
        return 0.8   # very long hair
    elif hair_ratio > 0.3:
        return 0.3   # medium-long
    elif hair_ratio < 0.1:
        return -0.5  # short hair
    else:
        return 0.0


def _detect_shoulder_width(
    alpha_mask: np.ndarray,
    landmarks: FaceLandmarks | None,
) -> float:
    """Detect shoulder width relative to head. Broad shoulders = male tendency."""
    if landmarks is None:
        return 0.0

    h, w = alpha_mask.shape
    fx, fy, fw, fh = landmarks.face_rect

    shoulder_y = landmarks.face_bottom + int(fh * 0.2)
    shoulder_y = min(shoulder_y, h - 1)

    shoulder_w = np.sum(alpha_mask[shoulder_y, :])
    head_w = fw

    if head_w < 10:
        return 0.0

    ratio = shoulder_w / head_w

    if ratio > 2.0:
        return -0.7   # very broad = male
    elif ratio > 1.6:
        return -0.3
    elif ratio < 1.1:
        return 0.5    # narrow shoulders = female
    elif ratio < 1.3:
        return 0.2
    else:
        return 0.0
