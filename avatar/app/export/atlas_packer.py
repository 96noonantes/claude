"""Pack multiple part PNGs into a single texture atlas.

Uses MaxRects bin-packing algorithm. No external dependencies.
Output: single atlas PNG + per-part UV region mapping.
"""

import numpy as np
from PIL import Image
from pathlib import Path
from dataclasses import dataclass


@dataclass
class AtlasRegion:
    x: int
    y: int
    w: int
    h: int


@dataclass
class AtlasResult:
    image: Image.Image
    width: int
    height: int
    regions: dict  # part_id → AtlasRegion


PADDING = 2  # px between parts (prevents texture bleed)


def pack_atlas(
    parts_data: list,
    parts_dir: Path,
    max_size: int = 2048,
) -> AtlasResult:
    """Pack all visible part PNGs into a single texture atlas.

    Args:
        parts_data: list of PartData objects
        parts_dir: directory containing part PNG files
        max_size: maximum atlas dimension (2048 for mobile safety)

    Returns:
        AtlasResult with packed atlas image and region mapping
    """
    # Load images and sort by area (largest first for better packing)
    items = []
    for part in parts_data:
        if not part.visible or not part.image_filename:
            continue
        path = parts_dir / part.image_filename
        if not path.exists():
            continue
        img = Image.open(path).convert("RGBA")
        items.append((part.id, img, img.width + PADDING, img.height + PADDING))

    items.sort(key=lambda x: x[2] * x[3], reverse=True)

    # Filter out parts larger than max atlas size
    items = [(pid, img, pw, ph) for pid, img, pw, ph in items
             if pw <= max_size and ph <= max_size]

    # Determine atlas size
    total_area = sum(w * h for _, _, w, h in items)
    atlas_size = 512
    while atlas_size * atlas_size < total_area * 1.3:
        atlas_size *= 2
    atlas_size = min(atlas_size, max_size)

    # MaxRects packing (with retry at larger sizes)
    for attempt in range(4):  # max 4 doublings: 512→1024→2048→4096
        regions = {}
        free_rects = [_Rect(0, 0, atlas_size, atlas_size)]
        all_placed = True

        for part_id, img, pw, ph in items:
            best_rect = None
            best_idx = -1
            best_score = float('inf')

            for i, rect in enumerate(free_rects):
                if pw <= rect.w and ph <= rect.h:
                    score = min(rect.w - pw, rect.h - ph)
                    if score < best_score:
                        best_score = score
                        best_rect = rect
                        best_idx = i

            if best_rect is None:
                all_placed = False
                break

            # Place part
            x, y = best_rect.x, best_rect.y
            regions[part_id] = AtlasRegion(x, y, img.width, img.height)

            # Split free rect
            del free_rects[best_idx]
            if best_rect.w - pw > 0:
                free_rects.append(_Rect(x + pw, y, best_rect.w - pw, ph))
            if best_rect.h - ph > 0:
                free_rects.append(_Rect(x, y + ph, best_rect.w, best_rect.h - ph))
            _prune_free_rects(free_rects)

        if all_placed:
            break

        # Retry with larger atlas
        if atlas_size < max_size:
            atlas_size = min(atlas_size * 2, max_size)
        else:
            break  # Can't grow further, use what we have

    # Compose atlas image
    atlas = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0))
    for part_id, img, _, _ in items:
        if part_id in regions:
            r = regions[part_id]
            atlas.paste(img, (r.x, r.y))

    return AtlasResult(
        image=atlas,
        width=atlas_size,
        height=atlas_size,
        regions=regions,
    )


def remap_mesh_uvs(
    mesh_uvs: list,
    region: AtlasRegion,
    atlas_w: int,
    atlas_h: int,
) -> list:
    """Remap mesh UVs from part-local (0-1) to atlas space (0-1).

    Args:
        mesh_uvs: [[u, v], ...] in part-local 0-1 coords
        region: AtlasRegion for this part
        atlas_w, atlas_h: atlas dimensions

    Returns:
        [[u, v], ...] in atlas 0-1 coords
    """
    remapped = []
    for u, v in mesh_uvs:
        au = (region.x + u * region.w) / atlas_w
        av = (region.y + v * region.h) / atlas_h
        remapped.append([round(au, 6), round(av, 6)])
    return remapped


class _Rect:
    __slots__ = ('x', 'y', 'w', 'h')

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


def _prune_free_rects(rects: list) -> None:
    """Remove free rects fully contained by another."""
    to_remove = set()
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i == j or i in to_remove or j in to_remove:
                continue
            a, b = rects[i], rects[j]
            if (a.x >= b.x and a.y >= b.y and
                    a.x + a.w <= b.x + b.w and a.y + a.h <= b.y + b.h):
                to_remove.add(i)
    for idx in sorted(to_remove, reverse=True):
        del rects[idx]
