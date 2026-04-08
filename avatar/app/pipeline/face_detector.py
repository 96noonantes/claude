"""Anime face landmark detection using OpenCV cascade + heuristic landmark estimation."""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass


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


def detect_anime_face(image_rgba: np.ndarray) -> FaceLandmarks | None:
    """Detect anime face and estimate landmark positions using OpenCV + heuristics.

    Uses the lbpcascade_animeface cascade classifier if available,
    otherwise falls back to haarcascade_frontalface with adjusted parameters.
    """
    gray = cv2.cvtColor(image_rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    face_rect = _detect_face_rect(gray)
    if face_rect is None:
        face_rect = _estimate_face_from_alpha(image_rgba)
    if face_rect is None:
        return None

    fx, fy, fw, fh = face_rect
    fc_x = fx + fw // 2
    fc_y = fy + fh // 2

    eye_y = fy + int(fh * 0.35)
    eye_w = int(fw * 0.22)
    eye_h = int(fh * 0.15)
    left_eye_cx = fx + int(fw * 0.32)
    right_eye_cx = fx + int(fw * 0.68)

    left_eye_rect = (
        left_eye_cx - eye_w, eye_y - eye_h // 2,
        eye_w * 2, eye_h,
    )
    right_eye_rect = (
        right_eye_cx - eye_w, eye_y - eye_h // 2,
        eye_w * 2, eye_h,
    )

    brow_y = eye_y - int(fh * 0.10)
    brow_h = int(fh * 0.08)
    left_eyebrow_rect = (
        left_eye_cx - eye_w, brow_y - brow_h // 2,
        eye_w * 2, brow_h,
    )
    right_eyebrow_rect = (
        right_eye_cx - eye_w, brow_y - brow_h // 2,
        eye_w * 2, brow_h,
    )

    nose_y = fy + int(fh * 0.55)
    nose_w = int(fw * 0.12)
    nose_h = int(fh * 0.10)
    nose_rect = (fc_x - nose_w, nose_y - nose_h // 2, nose_w * 2, nose_h)

    mouth_y = fy + int(fh * 0.72)
    mouth_w = int(fw * 0.18)
    mouth_h = int(fh * 0.10)
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
        face_bottom=fy + fh,
    )


def _detect_face_rect(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Try OpenCV cascade classifiers for face detection."""
    cascade_files = [
        "lbpcascade_animeface.xml",
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
    ]

    for cascade_path in cascade_files:
        if not Path(cascade_path).exists() and cascade_path == "lbpcascade_animeface.xml":
            continue
        try:
            cascade = cv2.CascadeClassifier(cascade_path)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(50, 50))
            if len(faces) > 0:
                faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                x, y, w, h = faces_sorted[0]
                return (int(x), int(y), int(w), int(h))
        except Exception:
            continue
    return None


def _estimate_face_from_alpha(image_rgba: np.ndarray) -> tuple[int, int, int, int] | None:
    """Estimate face region from alpha channel (top portion of the character)."""
    alpha = image_rgba[:, :, 3]
    if alpha.max() < 10:
        return None

    rows = np.any(alpha > 128, axis=1)
    cols = np.any(alpha > 128, axis=0)
    if not rows.any() or not cols.any():
        return None

    top = np.argmax(rows)
    bottom = len(rows) - np.argmax(rows[::-1])
    left = np.argmax(cols)
    right = len(cols) - np.argmax(cols[::-1])

    char_h = bottom - top
    char_w = right - left
    char_cx = (left + right) // 2

    face_w = int(char_w * 0.5)
    face_h = int(char_h * 0.3)
    face_x = char_cx - face_w // 2
    face_y = top + int(char_h * 0.02)

    return (face_x, face_y, face_w, face_h)
