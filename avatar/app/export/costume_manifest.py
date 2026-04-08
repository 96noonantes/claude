"""Generate costume.json manifest for cross-avatar dress-up compatibility."""

import json
from pathlib import Path

from app.models.session import SessionData


CLOTHING_CATEGORIES = {
    "tops", "bottoms_skirt", "bottoms_pants", "one_piece", "outer",
    "underwear_top", "underwear_bottom", "socks", "shoes", "hat",
    "collar", "gloves", "sleeve", "accessory", "costume",
}


def generate_costume_manifest(session: SessionData, output_path: Path) -> None:
    """Generate costume.json containing normalized costume data for dress-up."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bp = session.body_profile
    source_profile = {
        "height": bp.height,
        "body_type": bp.body_type,
        "head_ratio": bp.head_ratio,
        "shoulder_width": bp.shoulder_width,
        "waist_width": bp.waist_width,
        "hip_width": bp.hip_width,
        "leg_ratio": bp.leg_ratio,
    }

    costume_parts = []
    for part in session.parts:
        if not part.visible:
            continue
        if part.category not in CLOTHING_CATEGORIES:
            continue

        costume_parts.append({
            "id": part.id,
            "label": part.label,
            "category": part.category,
            "gender": part.gender,
            "normalized_bounds": part.normalized_bounds,
            "anchor": part.anchor,
            "fit_points": part.fit_points,
            "depth_order": part.depth_order,
            "image": f"parts/{part.image_filename}",
        })

    manifest = {
        "format_version": "1.0",
        "source_body_profile": source_profile,
        "detected_gender": _get_dominant_gender(session.parts),
        "parts": costume_parts,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _get_dominant_gender(parts) -> str:
    genders = [p.gender for p in parts if p.gender and p.gender != "unisex"]
    if not genders:
        return "unisex"
    female = genders.count("female")
    male = genders.count("male")
    return "female" if female >= male else "male"
