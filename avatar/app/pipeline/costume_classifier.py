"""Automatic costume category and gender classification.

Classifies each clothing part into detailed categories (14 types)
and assigns gender labels (male/female/unisex) based on shape analysis
and the character's detected gender.
"""

import cv2
import numpy as np
from pathlib import Path

from app.models.session import PartData
from app.pipeline.gender_detector import GenderResult
from app.pipeline.face_detector import FaceLandmarks
from app.pipeline.part_labels import (
    C_TOPS, C_BOTTOMS_SKIRT, C_BOTTOMS_PANTS, C_ONE_PIECE, C_OUTER,
    C_UNDERWEAR_TOP, C_UNDERWEAR_BOTTOM, C_SOCKS, C_SHOES, C_HAT,
    C_COLLAR, C_GLOVES, C_SLEEVE, C_ACCESSORY, C_COSTUME,
    C_HAIR, C_FACE, C_BODY, C_LIMB,
    G_MALE, G_FEMALE, G_UNISEX,
    get_category, get_default_gender,
)

# Clothing labels that need classification
CLOTHING_LABELS = {
    "outerwear_upper", "outerwear_lower", "underwear",
    "collar", "sleeve_left", "sleeve_right",
    "legwear", "footwear", "headwear", "accessory", "costume_full",
}


def classify_costume_parts(
    parts: list[PartData],
    gender_result: GenderResult,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    parts_dir: Path,
) -> list[PartData]:
    """Classify each part's category and gender.

    Non-clothing parts get their default category from part_labels.
    Clothing parts are analyzed for shape-based category refinement.
    """
    h, w = no_bg.shape[:2]
    alpha_mask = no_bg[:, :, 3] > 128
    char_gender = gender_result.gender

    for part in parts:
        # Set default category from part_labels
        default_cat = get_category(part.label)
        default_gen = get_default_gender(part.label)

        if part.label not in CLOTHING_LABELS:
            part.category = default_cat
            part.gender = default_gen
            continue

        # Load part image for shape analysis
        part_img = _load_part_image(part, parts_dir)

        if part.label == "outerwear_lower":
            cat, gen = _classify_bottom(part, part_img, gender_result, no_bg, landmarks, alpha_mask)
        elif part.label == "outerwear_upper":
            cat, gen = _classify_top(part, part_img, gender_result, no_bg, landmarks, alpha_mask)
        elif part.label == "underwear":
            cat, gen = _classify_underwear(part, part_img, gender_result)
        elif part.label == "legwear":
            cat, gen = _classify_legwear(part, part_img, gender_result)
        elif part.label == "footwear":
            cat, gen = _classify_footwear(part, part_img, gender_result)
        elif part.label == "headwear":
            cat, gen = _classify_headwear(part, part_img, gender_result)
        elif part.label == "collar":
            cat, gen = _classify_collar(part, part_img, gender_result)
        elif part.label in ("sleeve_left", "sleeve_right"):
            cat, gen = C_SLEEVE, G_UNISEX
        elif part.label == "accessory":
            cat, gen = C_ACCESSORY, G_UNISEX
        elif part.label == "costume_full":
            cat, gen = C_COSTUME, char_gender if gender_result.confidence > 0.5 else G_UNISEX
        else:
            cat, gen = default_cat, default_gen

        part.category = cat
        part.gender = gen

    return parts


def _load_part_image(part: PartData, parts_dir: Path) -> np.ndarray | None:
    """Load a part's PNG image as numpy array."""
    path = parts_dir / part.image_filename
    if not path.exists():
        return None
    from PIL import Image
    return np.array(Image.open(path).convert("RGBA"))


def _classify_bottom(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    alpha_mask: np.ndarray,
) -> tuple[str, str]:
    """Classify lower body clothing: skirt vs pants vs one-piece."""
    if part_img is None:
        return C_BOTTOMS_PANTS, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape

    if ph < 10 or pw < 10:
        return C_BOTTOMS_PANTS, G_UNISEX

    # Analyze width profile top to bottom
    row_widths = np.sum(part_alpha, axis=1).astype(float)
    nonzero = row_widths > 0
    if nonzero.sum() < 5:
        return C_BOTTOMS_PANTS, G_UNISEX

    first_row = int(np.argmax(nonzero))
    last_row = int(len(nonzero) - np.argmax(nonzero[::-1]))
    active_widths = row_widths[first_row:last_row]

    if len(active_widths) < 5:
        return C_BOTTOMS_PANTS, G_UNISEX

    # Smooth
    kernel = np.ones(max(3, len(active_widths) // 10)) / max(3, len(active_widths) // 10)
    smoothed = np.convolve(active_widths, kernel, mode='same')

    top_width = np.mean(smoothed[:len(smoothed) // 4])
    bottom_width = np.mean(smoothed[3 * len(smoothed) // 4:])
    mid_width = np.mean(smoothed[len(smoothed) // 3:2 * len(smoothed) // 3])

    if top_width < 5:
        return C_BOTTOMS_PANTS, G_UNISEX

    flare = bottom_width / top_width
    mid_flare = mid_width / top_width

    # Check for center gap (pants have a gap between legs)
    mid_row_idx = first_row + len(active_widths) // 2
    if mid_row_idx < ph:
        mid_row = part_alpha[mid_row_idx, :]
        if mid_row.any():
            cols = np.where(mid_row)[0]
            gaps = np.diff(cols)
            has_gap = np.any(gaps > pw * 0.1)
        else:
            has_gap = False
    else:
        has_gap = False

    # Decision
    if flare > 1.25 and mid_flare > 1.1 and not has_gap:
        # Flares out without center gap = skirt
        return C_BOTTOMS_SKIRT, G_FEMALE
    elif has_gap:
        # Center gap = pants/shorts
        return C_BOTTOMS_PANTS, G_UNISEX
    elif flare < 0.9:
        # Narrows = pants
        return C_BOTTOMS_PANTS, G_UNISEX
    else:
        # Ambiguous: use character gender as hint
        if gender_result.gender == "female" and gender_result.confidence > 0.4:
            return C_BOTTOMS_SKIRT, G_FEMALE
        return C_BOTTOMS_PANTS, G_UNISEX


def _classify_top(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
    no_bg: np.ndarray,
    landmarks: FaceLandmarks | None,
    alpha_mask: np.ndarray,
) -> tuple[str, str]:
    """Classify upper body clothing: tops vs outer vs one-piece."""
    if part_img is None:
        return C_TOPS, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape

    bx, by = part.bounds["x"], part.bounds["y"]
    bh = part.bounds["height"]

    h, w = no_bg.shape[:2]

    # Check if this extends far below waist (one-piece/dress)
    char_rows = np.any(alpha_mask, axis=1)
    if char_rows.any():
        char_top = int(np.argmax(char_rows))
        char_bottom = int(len(char_rows) - np.argmax(char_rows[::-1]))
        char_height = char_bottom - char_top

        part_bottom = by + bh
        part_extent = (part_bottom - char_top) / max(char_height, 1)

        # If the "upper" clothing extends past 60% of body height, it's a one-piece
        if part_extent > 0.6:
            gen = G_FEMALE if gender_result.gender == "female" else G_UNISEX
            return C_ONE_PIECE, gen

    # Check layering: if there are multiple clothing parts, outer one might be a jacket
    # For now, default to tops
    return C_TOPS, G_UNISEX


def _classify_underwear(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
) -> tuple[str, str]:
    """Classify underwear: top (bra) vs bottom."""
    if part_img is None:
        return C_UNDERWEAR_BOTTOM, G_UNISEX

    # Position-based: upper body = bra, lower = panties
    by = part.bounds.get("y", 0)
    bh = part.bounds.get("height", 0)

    # Small area + high position → bra/female underwear top
    if bh < 100:
        if gender_result.gender == "female":
            return C_UNDERWEAR_TOP, G_FEMALE
        return C_UNDERWEAR_BOTTOM, G_UNISEX

    return C_UNDERWEAR_BOTTOM, G_UNISEX


def _classify_legwear(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
) -> tuple[str, str]:
    """Classify legwear: socks, stockings, tights."""
    if part_img is None:
        return C_SOCKS, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape

    # Tall legwear (thigh-high, stockings) is typically female
    aspect = ph / max(pw, 1)
    if aspect > 3.0:
        return C_SOCKS, G_FEMALE  # thigh-high = typically female
    elif aspect > 1.5:
        return C_SOCKS, G_FEMALE  # knee-high = typically female

    return C_SOCKS, G_UNISEX


def _classify_footwear(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
) -> tuple[str, str]:
    """Classify footwear."""
    if part_img is None:
        return C_SHOES, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape

    # Tall footwear (boots) with narrow shape → heels (female tendency)
    aspect = ph / max(pw, 1)
    if aspect > 2.0:
        # Tall boots - check if narrow (heels)
        bottom_width = np.sum(part_alpha[-max(1, ph // 5):, :]) / max(1, ph // 5)
        if bottom_width < pw * 0.4:
            return C_SHOES, G_FEMALE  # high heels / narrow boots

    return C_SHOES, G_UNISEX


def _classify_headwear(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
) -> tuple[str, str]:
    """Classify headwear: hat, ribbon, tiara, etc."""
    if part_img is None:
        return C_HAT, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape
    area = part_alpha.sum()

    # Small headwear = hair accessory/ribbon (female tendency)
    if area < 2000:
        if gender_result.gender == "female":
            return C_HAT, G_FEMALE  # small = ribbon/hairpin

    return C_HAT, G_UNISEX


def _classify_collar(
    part: PartData,
    part_img: np.ndarray | None,
    gender_result: GenderResult,
) -> tuple[str, str]:
    """Classify collar/neckwear: tie, ribbon, choker."""
    if part_img is None:
        return C_COLLAR, G_UNISEX

    part_alpha = part_img[:, :, 3] > 30
    ph, pw = part_alpha.shape

    # Tall narrow shape = necktie (male tendency)
    aspect = ph / max(pw, 1)
    if aspect > 3.0:
        return C_COLLAR, G_MALE  # necktie

    # Wide short shape = bow/ribbon (female tendency)
    if aspect < 0.7 and pw > 30:
        return C_COLLAR, G_FEMALE  # ribbon bow

    return C_COLLAR, G_UNISEX
