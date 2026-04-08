"""Occlusion-aware inpainting for Live2D part layers.

When a character is drawn, parts overlap each other (hair over face,
clothing over body, etc.). For Live2D, each part needs to be complete
underneath so that toggling layers looks natural.

This module detects which parts are occluded by other parts, and uses
multi-strategy inpainting to reconstruct hidden regions:
1. Texture-aware OpenCV inpainting (Telea + Navier-Stokes blend)
2. Mirror-based symmetry fill (for symmetric parts like face/body)
3. Color-propagation fill (extends neighboring pixel colors smoothly)
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from scipy import ndimage

from app.models.session import PartData

# Parts sorted by depth (front to back). Front parts occlude back parts.
# Higher depth_order = rendered on top = can occlude lower parts.
OCCLUSION_RULES = {
    # Part that gets occluded → list of parts that can occlude it
    "face": ["hair_front", "hair_side_left", "hair_side_right"],
    "body_skin": ["outerwear_upper", "outerwear_lower", "hair_back", "hair_side_left", "hair_side_right"],
    "neck": ["hair_side_left", "hair_side_right", "outerwear_upper", "collar"],
    "eye_white_left": ["hair_front"],
    "eye_white_right": ["hair_front"],
    "iris_left": ["hair_front"],
    "iris_right": ["hair_front"],
    "eye_left": ["hair_front"],
    "eye_right": ["hair_front"],
    "eyebrow_left": ["hair_front"],
    "eyebrow_right": ["hair_front"],
    "upper_arm_left": ["outerwear_upper", "sleeve_left", "hair_side_left"],
    "upper_arm_right": ["outerwear_upper", "sleeve_right", "hair_side_right"],
    "forearm_left": ["sleeve_left"],
    "forearm_right": ["sleeve_right"],
    "thigh_left": ["outerwear_lower"],
    "thigh_right": ["outerwear_lower"],
    "shin_left": ["legwear"],
    "shin_right": ["legwear"],
    "hair_back": ["face", "body_skin", "body", "outerwear_upper"],
}


def inpaint_occluded_parts(
    no_bg: np.ndarray,
    parts: list[PartData],
    parts_dir: Path,
) -> list[PartData]:
    """Post-process all parts: detect and inpaint occluded regions.

    For each part, finds overlapping higher-depth parts and fills in
    the hidden regions using multi-strategy inpainting.

    Modifies part images in-place on disk.
    """
    h, w = no_bg.shape[:2]

    # Load all part masks
    part_masks: dict[str, np.ndarray] = {}
    part_images: dict[str, np.ndarray] = {}
    for part in parts:
        img_path = parts_dir / part.image_filename
        if not img_path.exists():
            continue
        img = np.array(Image.open(img_path).convert("RGBA"))

        # Reconstruct full-size mask from bounds + part image
        full_mask = np.zeros((h, w), dtype=bool)
        full_img = np.zeros((h, w, 4), dtype=np.uint8)
        bx, by = part.bounds["x"], part.bounds["y"]
        bw, bh = part.bounds["width"], part.bounds["height"]
        ph, pw = img.shape[:2]
        # Clamp to image bounds
        copy_h = min(ph, h - by, bh)
        copy_w = min(pw, w - bx, bw)
        if copy_h > 0 and copy_w > 0:
            full_mask[by:by + copy_h, bx:bx + copy_w] = img[:copy_h, :copy_w, 3] > 30
            full_img[by:by + copy_h, bx:bx + copy_w] = img[:copy_h, :copy_w]

        part_masks[part.label] = full_mask
        part_images[part.label] = full_img

    # For each part, compute and inpaint occluded regions
    for part in parts:
        if part.label not in part_masks:
            continue

        occluders = OCCLUSION_RULES.get(part.label, [])
        if not occluders:
            continue

        # Compute combined occlusion mask from all overlapping higher parts
        occlusion_mask = np.zeros((h, w), dtype=bool)
        for occluder_label in occluders:
            if occluder_label in part_masks:
                occlusion_mask |= part_masks[occluder_label]

        # The hidden region: area that SHOULD belong to this part but is covered
        current_mask = part_masks[part.label]
        # Estimate the full extent of this part (expand current visible area into occluded region)
        hidden_region = _estimate_hidden_region(current_mask, occlusion_mask, no_bg, part.label)

        if hidden_region.sum() < 20:
            continue

        # Inpaint the hidden region
        full_img = part_images[part.label]
        inpainted = _inpaint_region(full_img, current_mask, hidden_region, no_bg, part.label)

        if inpainted is None:
            continue

        # Update the part image
        expanded_mask = current_mask | hidden_region
        part_images[part.label] = inpainted
        part_masks[part.label] = expanded_mask

        # Save updated part image (crop to new bounds)
        _save_updated_part(inpainted, expanded_mask, part, parts_dir, h, w)

    return parts


def _estimate_hidden_region(
    visible_mask: np.ndarray,
    occlusion_mask: np.ndarray,
    no_bg: np.ndarray,
    part_label: str,
) -> np.ndarray:
    """Estimate which pixels in the occluded area should belong to this part.

    Strategy: dilate the visible part mask into the occluded area.
    The amount of dilation depends on the part type.
    """
    h, w = visible_mask.shape

    if visible_mask.sum() < 50:
        return np.zeros((h, w), dtype=bool)

    # How far to extend into the occluded area
    if part_label in ("face", "body_skin", "body", "neck"):
        dilation_px = 80  # Face/body extends significantly under hair/clothing
    elif "arm" in part_label or "leg" in part_label or "thigh" in part_label or "shin" in part_label:
        dilation_px = 40
    elif "eye" in part_label or "iris" in part_label:
        dilation_px = 15
    elif "eyebrow" in part_label:
        dilation_px = 10
    elif "hair_back" in part_label:
        dilation_px = 60
    else:
        dilation_px = 30

    # Dilate the visible mask to estimate full extent
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
    dilated = cv2.dilate(visible_mask.astype(np.uint8) * 255, kernel, iterations=1)
    estimated_full = dilated > 0

    # Hidden region = dilated area that overlaps with the occlusion mask
    hidden = estimated_full & occlusion_mask & ~visible_mask

    # For face, use the face ellipse to constrain the estimated region
    # (don't extend face pixels into hair area above the head)
    if part_label == "face":
        # Use connected components: keep only regions connected to the visible mask
        combined = (visible_mask | hidden).astype(np.uint8)
        labeled, num = ndimage.label(combined)
        # Keep only labels that overlap with visible mask
        visible_labels = set(np.unique(labeled[visible_mask]))
        visible_labels.discard(0)
        keep = np.zeros_like(combined, dtype=bool)
        for lbl in visible_labels:
            keep |= (labeled == lbl)
        hidden = keep & ~visible_mask

    return hidden


def _inpaint_region(
    part_rgba: np.ndarray,
    visible_mask: np.ndarray,
    hidden_region: np.ndarray,
    no_bg: np.ndarray,
    part_label: str,
) -> np.ndarray | None:
    """Inpaint the hidden region of a part using multiple strategies.

    Strategy priority:
    1. Mirror fill (for symmetric parts: face, body)
    2. OpenCV Telea inpainting
    3. Nearest-neighbor color propagation
    """
    h, w = part_rgba.shape[:2]

    if hidden_region.sum() < 10:
        return None

    result = part_rgba.copy()
    remaining_mask = hidden_region.copy()

    # Strategy 1: Mirror fill for symmetric parts
    if part_label in ("face", "body_skin", "body", "neck"):
        result, remaining_mask = _mirror_fill(result, visible_mask, remaining_mask, part_label)

    # Strategy 2: OpenCV inpainting (Telea + Navier-Stokes blend)
    if remaining_mask.sum() > 10:
        result, remaining_mask = _opencv_inpaint(result, visible_mask | (hidden_region & ~remaining_mask), remaining_mask, no_bg)

    # Strategy 3: Nearest-neighbor color propagation for remaining pixels
    if remaining_mask.sum() > 5:
        result = _color_propagation(result, visible_mask | (hidden_region & ~remaining_mask), remaining_mask)

    # Set alpha for filled regions
    filled = hidden_region & ~remaining_mask
    result[:, :, 3] = np.where(
        filled & (result[:, :, 3] < 128),
        np.uint8(255),
        result[:, :, 3],
    )

    return result


def _mirror_fill(
    rgba: np.ndarray,
    visible_mask: np.ndarray,
    to_fill: np.ndarray,
    part_label: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Fill occluded pixels by mirroring from the opposite side.

    Effective for roughly symmetric parts (face, body center).
    """
    h, w = rgba.shape[:2]

    # Find the symmetry axis (center X of the visible region)
    cols = np.any(visible_mask, axis=0)
    if not cols.any():
        return rgba, to_fill

    x_left = int(np.argmax(cols))
    x_right = int(len(cols) - np.argmax(cols[::-1]))
    center_x = (x_left + x_right) // 2

    result = rgba.copy()
    remaining = to_fill.copy()

    # For each pixel that needs filling, check if its mirror has data
    fill_ys, fill_xs = np.where(to_fill)

    for y, x in zip(fill_ys, fill_xs):
        mirror_x = 2 * center_x - x
        if 0 <= mirror_x < w and visible_mask[y, mirror_x]:
            result[y, x] = rgba[y, mirror_x]
            remaining[y, x] = False

    return result, remaining


def _opencv_inpaint(
    rgba: np.ndarray,
    known_mask: np.ndarray,
    to_fill: np.ndarray,
    no_bg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Inpaint using OpenCV (blend of Telea and Navier-Stokes)."""
    h, w = rgba.shape[:2]

    # Prepare source: use existing part pixels + original image as reference
    source_rgb = rgba[:, :, :3].copy()
    # In areas with no part data, use the original image as color hint
    no_data = ~known_mask & ~to_fill
    for c in range(3):
        source_rgb[:, :, c] = np.where(
            known_mask,
            rgba[:, :, c],
            no_bg[:, :, c],
        )

    inpaint_mask = to_fill.astype(np.uint8) * 255

    # Compute adaptive inpaint radius based on region size
    fill_rows = np.any(to_fill, axis=1)
    fill_cols = np.any(to_fill, axis=0)
    if not fill_rows.any():
        return rgba, to_fill

    fill_h = int(np.sum(fill_rows))
    fill_w = int(np.sum(fill_cols))
    radius = max(3, min(20, int((fill_h + fill_w) * 0.15)))

    try:
        # Telea method (better for large areas)
        telea = cv2.inpaint(source_rgb, inpaint_mask, radius, cv2.INPAINT_TELEA)
        # Navier-Stokes (better for texture continuity)
        ns = cv2.inpaint(source_rgb, inpaint_mask, radius, cv2.INPAINT_NS)

        # Blend: 60% Telea + 40% NS
        blended = cv2.addWeighted(telea, 0.6, ns, 0.4, 0)

        result = rgba.copy()
        for c in range(3):
            result[:, :, c] = np.where(to_fill, blended[:, :, c], rgba[:, :, c])
        result[:, :, 3] = np.where(to_fill, 255, rgba[:, :, 3])

        remaining = np.zeros_like(to_fill)
        return result, remaining
    except Exception:
        return rgba, to_fill


def _color_propagation(
    rgba: np.ndarray,
    known_mask: np.ndarray,
    to_fill: np.ndarray,
) -> np.ndarray:
    """Fill remaining pixels by propagating nearest known pixel colors."""
    if to_fill.sum() == 0:
        return rgba

    result = rgba.copy()

    # Distance transform from known pixels
    unknown = (~known_mask & to_fill).astype(np.uint8)
    if unknown.sum() == 0:
        return result

    # Find nearest known pixel for each unknown pixel
    dist, indices = ndimage.distance_transform_edt(unknown, return_indices=True)

    fill_ys, fill_xs = np.where(to_fill & ~known_mask)
    for y, x in zip(fill_ys, fill_xs):
        ny, nx = indices[0, y, x], indices[1, y, x]
        if known_mask[ny, nx]:
            result[y, x, :3] = rgba[ny, nx, :3]
            result[y, x, 3] = 255

    return result


def _save_updated_part(
    full_img: np.ndarray,
    expanded_mask: np.ndarray,
    part: PartData,
    parts_dir: Path,
    img_h: int,
    img_w: int,
) -> None:
    """Crop the updated full image to new bounds and save."""
    rows = np.any(expanded_mask, axis=1)
    cols = np.any(expanded_mask, axis=0)
    if not rows.any() or not cols.any():
        return

    y1 = max(0, int(np.argmax(rows)) - 3)
    y2 = min(img_h, int(len(rows) - np.argmax(rows[::-1])) + 3)
    x1 = max(0, int(np.argmax(cols)) - 3)
    x2 = min(img_w, int(len(cols) - np.argmax(cols[::-1])) + 3)

    cropped = full_img[y1:y2, x1:x2]

    # Update part bounds
    part.bounds = {
        "x": int(x1), "y": int(y1),
        "width": int(x2 - x1), "height": int(y2 - y1),
    }

    Image.fromarray(cropped).save(parts_dir / part.image_filename)
