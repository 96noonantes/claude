"""Generate avatar_runtime.json — single file containing everything a PWA needs
to render the avatar with WebGL on iPhone 15.

The PWA loads only atlas.png + avatar_runtime.json. No other files needed.
"""

import json
from dataclasses import asdict
from pathlib import Path

from PIL import Image
import numpy as np

from app.models.session import SessionData, PartData
from app.pipeline.mesh_generator import generate_mesh, MeshData
from app.pipeline.auto_rigger import auto_rig
from app.export.atlas_packer import pack_atlas, remap_mesh_uvs


def generate_runtime_data(session: SessionData) -> tuple[dict, Image.Image]:
    """Generate avatar_runtime.json content and atlas image.

    Returns:
        (runtime_dict, atlas_image)
    """
    parts = [p for p in session.parts if p.visible]

    # --- Pack texture atlas ---
    atlas_result = pack_atlas(parts, session.parts_dir)

    # --- Generate meshes, remap UVs, auto-rig ---
    runtime_parts = []
    for part in parts:
        # Load part image for mesh generation
        img_path = session.parts_dir / part.image_filename
        if not img_path.exists():
            continue

        part_img = np.array(Image.open(img_path).convert("RGBA"))

        # Generate mesh
        mesh = generate_mesh(part_img)

        # Remap UVs to atlas space
        if part.id in atlas_result.regions:
            region = atlas_result.regions[part.id]
            atlas_uvs = remap_mesh_uvs(
                mesh.uvs, region,
                atlas_result.width, atlas_result.height,
            )
        else:
            atlas_uvs = mesh.uvs

        # Auto-rig: generate deformers with vertex weights
        deformers = auto_rig(part.id, part.category, part.label, mesh.vertices)

        runtime_parts.append({
            "id": part.id,
            "label": part.label,
            "depth_order": part.depth_order,
            "position": {"x": part.bounds.get("x", 0), "y": part.bounds.get("y", 0)},
            "size": {"w": part.bounds.get("width", 0), "h": part.bounds.get("height", 0)},
            "category": part.category,
            "gender": part.gender,
            "mesh": {
                "vertices": mesh.vertices,
                "uvs": atlas_uvs,
                "indices": mesh.indices,
                "vertex_count": mesh.vertex_count,
                "triangle_count": mesh.triangle_count,
            },
            "deformers": deformers,
        })

    # --- Build parameters list ---
    parameters = _build_parameters(parts)

    # --- Physics ---
    physics = _build_physics(parts)

    # --- Motions ---
    motions = _build_motions()

    # --- Expressions ---
    expressions = _build_expressions()

    # --- Body profile ---
    bp = session.body_profile
    body_profile = {
        "height": bp.height,
        "body_type": bp.body_type,
        "head_ratio": bp.head_ratio,
        "shoulder_width": bp.shoulder_width,
        "waist_width": bp.waist_width,
        "hip_width": bp.hip_width,
        "leg_ratio": bp.leg_ratio,
        "hair_color": bp.hair_color,
        "skin_color": bp.skin_color,
    }

    # --- Costume meta ---
    costume_parts = []
    for part in parts:
        if part.category in ("tops", "bottoms_skirt", "bottoms_pants", "one_piece",
                              "outer", "socks", "shoes", "hat", "collar", "sleeve",
                              "accessory", "costume", "underwear_top", "underwear_bottom"):
            costume_parts.append({
                "id": part.id,
                "category": part.category,
                "gender": part.gender,
                "normalized_bounds": part.normalized_bounds,
                "fit_points": part.fit_points,
            })

    runtime = {
        "format": "live2d-avatar-runtime",
        "version": "1.0",
        "canvas": {
            "width": session.image_width,
            "height": session.image_height,
        },
        "atlas": {
            "file": "atlas.png",
            "width": atlas_result.width,
            "height": atlas_result.height,
        },
        "parts": runtime_parts,
        "parameters": parameters,
        "physics": physics,
        "motions": motions,
        "expressions": expressions,
        "body_profile": body_profile,
        "costume_meta": {
            "detected_gender": _dominant_gender(parts),
            "parts": costume_parts,
        },
    }

    return runtime, atlas_result.image


def _build_parameters(parts):
    """Build parameter definitions."""
    params = [
        {"id": "eyeLOpen", "min": 0, "max": 1, "default": 1},
        {"id": "eyeROpen", "min": 0, "max": 1, "default": 1},
        {"id": "eyeLSmile", "min": 0, "max": 1, "default": 0},
        {"id": "eyeRSmile", "min": 0, "max": 1, "default": 0},
        {"id": "eyeBallX", "min": -1, "max": 1, "default": 0},
        {"id": "eyeBallY", "min": -1, "max": 1, "default": 0},
        {"id": "browLY", "min": -1, "max": 1, "default": 0},
        {"id": "browRY", "min": -1, "max": 1, "default": 0},
        {"id": "browLAngle", "min": -1, "max": 1, "default": 0},
        {"id": "browRAngle", "min": -1, "max": 1, "default": 0},
        {"id": "mouthOpenY", "min": 0, "max": 1, "default": 0},
        {"id": "mouthForm", "min": -1, "max": 1, "default": 0},
        {"id": "angleX", "min": -30, "max": 30, "default": 0},
        {"id": "angleY", "min": -30, "max": 30, "default": 0},
        {"id": "angleZ", "min": -30, "max": 30, "default": 0},
        {"id": "bodyAngleX", "min": -10, "max": 10, "default": 0},
        {"id": "breath", "min": 0, "max": 1, "default": 0},
    ]

    # Add hair physics params if hair parts exist
    hair_labels = {p.label for p in parts}
    if "hair_front" in hair_labels:
        params.append({"id": "hairFront", "min": -10, "max": 10, "default": 0})
    if "hair_back" in hair_labels:
        params.append({"id": "hairBack", "min": -10, "max": 10, "default": 0})
    if "hair_side_left" in hair_labels:
        params.append({"id": "hairSideL", "min": -10, "max": 10, "default": 0})
    if "hair_side_right" in hair_labels:
        params.append({"id": "hairSideR", "min": -10, "max": 10, "default": 0})

    # Skirt physics
    labels = {p.label for p in parts}
    if "outerwear_lower" in labels:
        params.append({"id": "skirtCenter", "min": -10, "max": 10, "default": 0})

    return params


def _build_physics(parts):
    """Build physics simulation definitions."""
    physics = []
    labels = {p.label for p in parts}

    hair_defs = [
        ("hair_front", "angleX", "hairFront", 0.95, 0.8),
        ("hair_back", "angleX", "hairBack", 0.90, 0.6),
        ("hair_side_left", "angleX", "hairSideL", 0.92, 0.7),
        ("hair_side_right", "angleX", "hairSideR", 0.92, 0.7),
    ]
    for label, input_p, output_p, mobility, damping in hair_defs:
        if label in labels:
            physics.append({
                "id": label,
                "input_param": input_p,
                "output_param": output_p,
                "pendulum": {
                    "length": 5.0,
                    "mobility": mobility,
                    "damping": damping,
                    "gravity": -1.0,
                },
            })

    if "outerwear_lower" in labels:
        physics.append({
            "id": "skirt",
            "input_param": "bodyAngleX",
            "output_param": "skirtCenter",
            "pendulum": {
                "length": 8.0,
                "mobility": 0.85,
                "damping": 0.5,
                "gravity": -1.0,
            },
        })

    return physics


def _build_motions():
    """Build idle and blink motion data inline."""
    return {
        "idle": {
            "duration": 8.0,
            "loop": True,
            "fps": 30,
            "curves": {
                "angleX": _sine_curve(8.0, 30, 3.0, 0.7),
                "angleY": _sine_curve(8.0, 30, 2.0, 0.5),
                "angleZ": _sine_curve(8.0, 30, 1.5, 0.3),
                "bodyAngleX": _sine_curve(8.0, 30, 1.0, 0.7),
                "breath": _sine_curve(8.0, 30, 0.5, 1.8, offset=0.5),
            },
        },
        "blink": {
            "duration": 0.4,
            "loop": False,
            "fps": 30,
            "curves": {
                "eyeLOpen": [1.0, 0.9, 0.7, 0.4, 0.1, 0.0, 0.0, 0.1, 0.4, 0.7, 0.9, 1.0],
                "eyeROpen": [1.0, 0.9, 0.7, 0.4, 0.1, 0.0, 0.0, 0.1, 0.4, 0.7, 0.9, 1.0],
            },
        },
    }


def _sine_curve(duration, fps, amplitude, frequency, offset=0.0):
    """Generate a sine wave as keyframe values."""
    import math
    frames = int(duration * fps)
    return [round(offset + amplitude * math.sin(2 * math.pi * frequency * t / fps), 3)
            for t in range(frames)]


def _build_expressions():
    """Build expression presets."""
    # Must match EXPRESSIONS in animationEngine.js
    return {
        "neutral": {},
        "happy": {"eyeLSmile": 1.0, "eyeRSmile": 1.0, "eyeLOpen": 0.7, "eyeROpen": 0.7, "mouthForm": 1.0, "mouthOpenY": 0.3, "browLY": 0.3, "browRY": 0.3},
        "sad": {"eyeLOpen": 0.6, "eyeROpen": 0.6, "mouthForm": -0.7, "browLY": -0.5, "browRY": -0.5, "browLAngle": -0.6, "browRAngle": -0.6},
        "angry": {"eyeLOpen": 0.9, "eyeROpen": 0.9, "mouthForm": -0.5, "mouthOpenY": 0.2, "browLY": -0.3, "browRY": -0.3, "browLAngle": 0.8, "browRAngle": 0.8},
        "surprised": {"eyeLOpen": 1.0, "eyeROpen": 1.0, "mouthOpenY": 0.8, "browLY": 0.8, "browRY": 0.8},
        "embarrassed": {"eyeLSmile": 0.6, "eyeRSmile": 0.6, "eyeLOpen": 0.5, "eyeROpen": 0.5, "mouthForm": 0.4, "browLY": 0.2, "browRY": 0.2},
        "wink_left": {"eyeLOpen": 0.0, "eyeROpen": 1.0, "eyeLSmile": 0.8, "mouthForm": 0.7},
        "sleepy": {"eyeLOpen": 0.2, "eyeROpen": 0.2, "mouthOpenY": 0.5, "browLY": -0.3, "browRY": -0.3},
        "smug": {"eyeLOpen": 0.6, "eyeROpen": 0.6, "eyeLSmile": 0.5, "eyeRSmile": 0.5, "mouthForm": 0.8, "browLY": 0.2, "browRY": -0.2, "browLAngle": 0.3},
    }


def _dominant_gender(parts):
    genders = [p.gender for p in parts if p.gender and p.gender != "unisex"]
    if not genders:
        return "unisex"
    return "female" if genders.count("female") >= genders.count("male") else "male"
