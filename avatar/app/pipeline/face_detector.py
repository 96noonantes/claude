"""Anime face landmark detection with multi-strategy detection and adaptive landmarks.

Improvements over v1:
- Uses lbpcascade_animeface.xml (anime-specific cascade)
- Multi-strategy fallback: anime cascade → haarcascade_alt2 → eye-pair inference → alpha heuristic
- Adaptive landmarks: detects actual eye positions within face, derives other landmarks relatively
- Face aspect ratio adaptation for different anime styles (chibi, realistic, standard)
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass

MODELS_DIR = Path(__file__).parent / "models"
ANIME_CASCADE_PATH = str(MODELS_DIR / "lbpcascade_animeface.xml")


@dataclass
class FaceLandmarks:
    face_rect: tuple[int, int, int, int]  # x, y, w, h
    left_eye_center: tuple[int, int]
    right_eye_center: tuple[int, int]
    left_eye_rect: tuple[int, int, int, int]
    right_eye_rect: tuple[int, int, int, int]
    left_eyebrow_rect: tuple[int, int, int, int]
    right_eyebrow_rect: tuple[int, int, int, int]
    nose_center: tuple[int, int]
    nose_rect: tuple[int, int, int, int]
    mouth_center: tuple[int, int]
    mouth_rect: tuple[int, int, int, int]
    face_center_x: int
    face_top: int
    face_bottom: int
    eye_detection_confidence: float = 0.0  # 0=estimated, 1=detected


def detect_anime_face(image_rgba: np.ndarray) -> FaceLandmarks | None:
    """Detect anime face with multi-strategy detection and adaptive landmarks."""
    gray = cv2.cvtColor(image_rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # Multi-strategy face detection
    face_rect = _detect_face_multi_strategy(gray, image_rgba)
    if face_rect is None:
        return None

    fx, fy, fw, fh = face_rect
    fc_x = fx + fw // 2

    # Try to detect actual eye positions within the face
    eyes_detected, left_eye, right_eye, confidence = _detect_eyes_in_face(gray, face_rect)

    if eyes_detected:
        landmarks = _build_landmarks_from_eyes(face_rect, left_eye, right_eye, confidence)
    else:
        landmarks = _build_landmarks_adaptive(face_rect)

    return landmarks


def _detect_face_multi_strategy(gray: np.ndarray, image_rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    """Try multiple strategies to detect the face, in order of reliability."""
    h, w = gray.shape

    # Strategy 1: lbpcascade_animeface (best for anime)
    result = _try_cascade(gray, ANIME_CASCADE_PATH, scale_factor=1.05, min_neighbors=5, min_size=(40, 40))
    if result:
        return result

    # Strategy 2: haarcascade_frontalface_alt2 (handles more angles)
    result = _try_cascade(
        gray,
        cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml",
        scale_factor=1.1, min_neighbors=3, min_size=(50, 50),
    )
    if result:
        return result

    # Strategy 3: Eye-pair detection → infer face rect from two eyes
    result = _detect_face_from_eye_pair(gray, image_rgba)
    if result:
        return result

    # Strategy 4: Skin color region analysis
    result = _detect_face_from_skin_color(image_rgba)
    if result:
        return result

    # Strategy 5: Improved alpha-channel heuristic
    result = _estimate_face_from_alpha_improved(image_rgba)
    return result


def _try_cascade(gray: np.ndarray, cascade_path: str, scale_factor: float = 1.1,
                 min_neighbors: int = 3, min_size: tuple = (50, 50)) -> tuple[int, int, int, int] | None:
    """Try a single cascade classifier."""
    if not Path(cascade_path).exists():
        return None
    try:
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return None
        faces = cascade.detectMultiScale(gray, scaleFactor=scale_factor,
                                          minNeighbors=min_neighbors, minSize=min_size)
        if len(faces) > 0:
            faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces_sorted[0]
            return (int(x), int(y), int(w), int(h))
    except Exception:
        pass
    return None


def _detect_face_from_eye_pair(gray: np.ndarray, image_rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    """Detect two eyes and infer face rectangle from eye positions."""
    h, w = gray.shape
    alpha = image_rgba[:, :, 3]

    # Only search in the upper 60% of the character
    rows = np.any(alpha > 128, axis=1)
    if not rows.any():
        return None
    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    search_bottom = top + int((bottom - top) * 0.6)

    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    if eye_cascade.empty():
        return None

    search_region = gray[top:search_bottom, :]
    eyes = eye_cascade.detectMultiScale(search_region, scaleFactor=1.1, minNeighbors=5, minSize=(15, 15))

    if len(eyes) < 2:
        return None

    # Filter by size similarity (both eyes should be similar size)
    eyes_sorted = sorted(eyes, key=lambda e: e[2] * e[3], reverse=True)
    for i in range(len(eyes_sorted)):
        for j in range(i + 1, len(eyes_sorted)):
            e1, e2 = eyes_sorted[i], eyes_sorted[j]
            size_ratio = min(e1[2] * e1[3], e2[2] * e2[3]) / max(e1[2] * e1[3], e2[2] * e2[3])
            if size_ratio < 0.4:
                continue

            # Eye centers
            c1x = e1[0] + e1[2] // 2
            c1y = top + e1[1] + e1[3] // 2
            c2x = e2[0] + e2[2] // 2
            c2y = top + e2[1] + e2[3] // 2

            inter_eye = abs(c1x - c2x)
            y_diff = abs(c1y - c2y)

            # Eyes should be roughly horizontal and reasonably spaced
            if y_diff > inter_eye * 0.4:
                continue
            if inter_eye < w * 0.05 or inter_eye > w * 0.5:
                continue

            # Infer face rect
            mid_x = (c1x + c2x) // 2
            mid_y = (c1y + c2y) // 2
            face_w = int(inter_eye * 2.2)
            face_h = int(face_w * 1.3)
            face_x = mid_x - face_w // 2
            face_y = mid_y - int(face_h * 0.35)

            face_x = max(0, face_x)
            face_y = max(0, face_y)
            face_w = min(face_w, w - face_x)
            face_h = min(face_h, h - face_y)

            return (face_x, face_y, face_w, face_h)

    return None


def _detect_face_from_skin_color(image_rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    """Detect face region using skin color analysis in YCrCb space."""
    h, w = image_rgba.shape[:2]
    alpha = image_rgba[:, :, 3]
    if alpha.max() < 10:
        return None

    rgb = image_rgba[:, :, :3]
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)

    # Broad skin color range for anime (lighter than real photos)
    skin_mask = cv2.inRange(ycrcb, np.array([50, 130, 75]), np.array([255, 180, 135]))
    skin_mask = skin_mask & (alpha > 128).astype(np.uint8) * 255

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Find the largest skin region in the upper half
    rows = np.any(alpha > 128, axis=1)
    char_top = int(np.argmax(rows))
    char_bottom = int(len(rows) - np.argmax(rows[::-1]))
    upper_limit = char_top + (char_bottom - char_top) // 2

    best = None
    best_area = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if y + ch // 2 > upper_limit:
            continue
        area = cv2.contourArea(cnt)
        if area > best_area:
            best_area = area
            best = (x, y, cw, ch)

    if best and best_area > 500:
        return best
    return None


def _estimate_face_from_alpha_improved(image_rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    """Improved alpha-channel heuristic using horizontal width distribution."""
    alpha = image_rgba[:, :, 3]
    h, w = alpha.shape

    if alpha.max() < 10:
        return None

    rows = np.any(alpha > 128, axis=1)
    cols = np.any(alpha > 128, axis=0)
    if not rows.any() or not cols.any():
        return None

    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))

    char_h = bottom - top
    char_w = right - left
    char_cx = (left + right) // 2

    # Analyze horizontal width distribution to find the head
    # The head is typically the widest point in the top third
    row_widths = np.sum(alpha[top:top + char_h // 3, :] > 128, axis=1)
    if len(row_widths) == 0:
        return None

    # Find the row with maximum width in the top region
    head_relative_y = int(np.argmax(row_widths))
    max_width = row_widths[head_relative_y]

    if max_width < 20:
        # Fallback to simple proportion
        face_w = int(char_w * 0.5)
        face_h = int(char_h * 0.3)
    else:
        face_w = int(max_width * 0.85)
        face_h = int(face_w * 1.2)

    face_x = char_cx - face_w // 2
    face_y = top + max(0, head_relative_y - face_h // 4)

    face_x = max(0, face_x)
    face_y = max(0, face_y)
    face_w = min(face_w, w - face_x)
    face_h = min(face_h, h - face_y)

    return (face_x, face_y, face_w, face_h)


def _detect_eyes_in_face(gray: np.ndarray, face_rect: tuple[int, int, int, int]) -> tuple[bool, tuple[int, int], tuple[int, int], float]:
    """Try to detect actual eye positions within the face rectangle.

    Returns (success, left_eye_center, right_eye_center, confidence).
    """
    fx, fy, fw, fh = face_rect

    # Search in the upper 60% of the face for eyes
    search_y1 = fy + int(fh * 0.15)
    search_y2 = fy + int(fh * 0.65)
    search_x1 = max(0, fx)
    search_x2 = min(gray.shape[1], fx + fw)

    face_region = gray[search_y1:search_y2, search_x1:search_x2]
    if face_region.size == 0:
        return False, (0, 0), (0, 0), 0.0

    # Try multiple eye cascades
    eye_cascades = [
        cv2.data.haarcascades + "haarcascade_eye.xml",
        cv2.data.haarcascades + "haarcascade_lefteye_2splits.xml",
    ]

    for cascade_path in eye_cascades:
        try:
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                continue
            eyes = cascade.detectMultiScale(face_region, scaleFactor=1.05, minNeighbors=4,
                                             minSize=(int(fw * 0.08), int(fh * 0.05)))
            if len(eyes) >= 2:
                # Sort by x position to get left and right
                eyes_sorted = sorted(eyes, key=lambda e: e[0])

                # Filter: pick two eyes that are roughly at the same height and similar size
                for i in range(len(eyes_sorted)):
                    for j in range(i + 1, len(eyes_sorted)):
                        e1, e2 = eyes_sorted[i], eyes_sorted[j]
                        # Size similarity
                        size_ratio = min(e1[2] * e1[3], e2[2] * e2[3]) / max(e1[2] * e1[3], e2[2] * e2[3])
                        if size_ratio < 0.3:
                            continue
                        # Height similarity
                        cy1 = e1[1] + e1[3] // 2
                        cy2 = e2[1] + e2[3] // 2
                        if abs(cy1 - cy2) > max(e1[3], e2[3]):
                            continue
                        # Horizontal separation
                        cx1 = e1[0] + e1[2] // 2
                        cx2 = e2[0] + e2[2] // 2
                        if abs(cx1 - cx2) < fw * 0.15:
                            continue

                        left_eye = (search_x1 + cx1, search_y1 + cy1)
                        right_eye = (search_x1 + cx2, search_y1 + cy2)
                        return True, left_eye, right_eye, 0.8
        except Exception:
            continue

    return False, (0, 0), (0, 0), 0.0


def _build_landmarks_from_eyes(
    face_rect: tuple[int, int, int, int],
    left_eye: tuple[int, int],
    right_eye: tuple[int, int],
    confidence: float,
) -> FaceLandmarks:
    """Build landmarks from detected eye positions, deriving other features relatively."""
    fx, fy, fw, fh = face_rect
    fc_x = fx + fw // 2
    face_bottom = fy + fh

    lex, ley = left_eye
    rex, rey = right_eye
    inter_eye = abs(rex - lex)
    eye_y = (ley + rey) // 2
    eye_mid_x = (lex + rex) // 2

    eye_w = int(inter_eye * 0.35)
    eye_h = int(inter_eye * 0.25)

    left_eye_rect = (lex - eye_w, ley - eye_h, eye_w * 2, eye_h * 2)
    right_eye_rect = (rex - eye_w, rey - eye_h, eye_w * 2, eye_h * 2)

    # Eyebrows: above eyes, distance based on inter-eye distance
    brow_offset = int(inter_eye * 0.25)
    brow_h = int(inter_eye * 0.12)
    left_eyebrow_rect = (lex - eye_w, ley - brow_offset - brow_h, eye_w * 2, brow_h)
    right_eyebrow_rect = (rex - eye_w, rey - brow_offset - brow_h, eye_w * 2, brow_h)

    # Nose: 35% of the distance from eyes to chin
    nose_y = eye_y + int((face_bottom - eye_y) * 0.35)
    nose_w = int(inter_eye * 0.20)
    nose_h = int(inter_eye * 0.15)
    nose_rect = (eye_mid_x - nose_w, nose_y - nose_h // 2, nose_w * 2, nose_h)

    # Mouth: 60% of the distance from eyes to chin
    mouth_y = eye_y + int((face_bottom - eye_y) * 0.60)
    mouth_w = int(inter_eye * 0.30)
    mouth_h = int(inter_eye * 0.15)
    mouth_rect = (eye_mid_x - mouth_w, mouth_y - mouth_h // 2, mouth_w * 2, mouth_h)

    return FaceLandmarks(
        face_rect=face_rect,
        left_eye_center=left_eye,
        right_eye_center=right_eye,
        left_eye_rect=left_eye_rect,
        right_eye_rect=right_eye_rect,
        left_eyebrow_rect=left_eyebrow_rect,
        right_eyebrow_rect=right_eyebrow_rect,
        nose_center=(eye_mid_x, nose_y),
        nose_rect=nose_rect,
        mouth_center=(eye_mid_x, mouth_y),
        mouth_rect=mouth_rect,
        face_center_x=eye_mid_x,
        face_top=fy,
        face_bottom=face_bottom,
        eye_detection_confidence=confidence,
    )


def _build_landmarks_adaptive(face_rect: tuple[int, int, int, int]) -> FaceLandmarks:
    """Build landmarks using adaptive proportions based on face aspect ratio."""
    fx, fy, fw, fh = face_rect
    fc_x = fx + fw // 2
    aspect = fh / max(fw, 1)

    # Adapt proportions based on face shape
    if aspect > 1.4:
        # Tall face (realistic style) - eyes higher
        eye_y_ratio = 0.32
        eye_x_spread = 0.34
    elif aspect < 1.0:
        # Wide face (chibi/SD) - eyes lower and wider
        eye_y_ratio = 0.42
        eye_x_spread = 0.28
    else:
        # Standard anime
        eye_y_ratio = 0.36
        eye_x_spread = 0.32

    eye_y = fy + int(fh * eye_y_ratio)
    left_eye_cx = fx + int(fw * eye_x_spread)
    right_eye_cx = fx + int(fw * (1 - eye_x_spread))
    inter_eye = right_eye_cx - left_eye_cx

    eye_w = int(fw * 0.20)
    eye_h = int(fh * 0.13)

    left_eye_rect = (left_eye_cx - eye_w, eye_y - eye_h // 2, eye_w * 2, eye_h)
    right_eye_rect = (right_eye_cx - eye_w, eye_y - eye_h // 2, eye_w * 2, eye_h)

    brow_y = eye_y - int(fh * 0.08)
    brow_h = int(fh * 0.06)
    left_eyebrow_rect = (left_eye_cx - eye_w, brow_y - brow_h // 2, eye_w * 2, brow_h)
    right_eyebrow_rect = (right_eye_cx - eye_w, brow_y - brow_h // 2, eye_w * 2, brow_h)

    face_bottom = fy + fh
    nose_y = eye_y + int((face_bottom - eye_y) * 0.35)
    nose_w = int(fw * 0.10)
    nose_h = int(fh * 0.08)
    nose_rect = (fc_x - nose_w, nose_y - nose_h // 2, nose_w * 2, nose_h)

    mouth_y = eye_y + int((face_bottom - eye_y) * 0.60)
    mouth_w = int(fw * 0.16)
    mouth_h = int(fh * 0.08)
    mouth_rect = (fc_x - mouth_w, mouth_y - mouth_h // 2, mouth_w * 2, mouth_h)

    return FaceLandmarks(
        face_rect=face_rect,
        left_eye_center=(left_eye_cx, eye_y),
        right_eye_center=(right_eye_cx, eye_y),
        left_eye_rect=left_eye_rect,
        right_eye_rect=right_eye_rect,
        left_eyebrow_rect=left_eyebrow_rect,
        right_eyebrow_rect=right_eyebrow_rect,
        nose_center=(fc_x, nose_y),
        nose_rect=nose_rect,
        mouth_center=(fc_x, mouth_y),
        mouth_rect=mouth_rect,
        face_center_x=fc_x,
        face_top=fy,
        face_bottom=face_bottom,
        eye_detection_confidence=0.0,
    )
