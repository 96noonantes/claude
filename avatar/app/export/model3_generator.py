"""Generate Live2D Cubism model3.json following CubismSpecs format."""

import json
from pathlib import Path

from app.models.session import SessionData


def generate_model3_json(session: SessionData, output_path: Path) -> None:
    """Generate a model3.json file conforming to Live2D CubismSpecs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    visible_parts = [p for p in session.parts if p.visible]

    has_eyes = any(p.label.startswith("eye_") for p in visible_parts)
    has_mouth = any(p.label == "mouth" for p in visible_parts)
    has_eyebrows = any(p.label.startswith("eyebrow_") for p in visible_parts)

    groups = []
    if has_eyes:
        groups.append({
            "Target": "Parameter",
            "Name": "EyeBlink",
            "Ids": ["ParamEyeLOpen", "ParamEyeROpen"],
        })
    if has_mouth:
        groups.append({
            "Target": "Parameter",
            "Name": "LipSync",
            "Ids": ["ParamMouthOpenY"],
        })

    hit_areas = []
    if any(p.label == "face" for p in visible_parts):
        hit_areas.append({"Id": "HitAreaHead", "Name": "Head"})
    if any(p.label == "body" for p in visible_parts):
        hit_areas.append({"Id": "HitAreaBody", "Name": "Body"})

    texture_files = []
    for p in visible_parts:
        texture_files.append(f"parts/{p.image_filename}")

    model3 = {
        "Version": 3,
        "FileReferences": {
            "Moc": "",
            "Textures": texture_files,
            "Physics": "physics3.json",
            "Motions": {
                "Idle": [{"File": "motions/idle.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5}],
            },
        },
        "Groups": groups,
        "HitAreas": hit_areas,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(model3, f, ensure_ascii=False, indent=2)


def generate_physics3_json(output_path: Path) -> None:
    """Generate a template physics3.json for hair physics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    physics = {
        "Version": 3,
        "Meta": {
            "PhysicsSettingCount": 1,
            "TotalInputCount": 1,
            "TotalOutputCount": 1,
            "VertexCount": 2,
            "Fps": 30.0,
            "EffectiveForces": {
                "Gravity": {"X": 0.0, "Y": -1.0},
                "Wind": {"X": 0.0, "Y": 0.0},
            },
            "PhysicsDictionary": [
                {"Id": "PhysicsSetting1", "Name": "Hair"},
            ],
        },
        "PhysicsSettings": [
            {
                "Id": "PhysicsSetting1",
                "Input": [
                    {
                        "Source": {"Target": "Parameter", "Id": "ParamAngleX"},
                        "Weight": 100,
                        "Type": "X",
                        "Reflect": False,
                    },
                ],
                "Output": [
                    {
                        "Destination": {"Target": "Parameter", "Id": "ParamHairFront"},
                        "VertexIndex": 1,
                        "Scale": 0.5,
                        "Weight": 100,
                        "Type": "Angle",
                        "Reflect": False,
                    },
                ],
                "Vertices": [
                    {"Position": {"X": 0.0, "Y": 0.0}, "Mobility": 1.0, "Delay": 1.0, "Acceleration": 1.0, "Radius": 0.0},
                    {"Position": {"X": 0.0, "Y": 5.0}, "Mobility": 0.95, "Delay": 0.8, "Acceleration": 1.5, "Radius": 3.0},
                ],
                "Normalization": {
                    "Position": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0},
                    "Angle": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0},
                },
            },
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(physics, f, ensure_ascii=False, indent=2)


def generate_motion3_json(output_path: Path) -> None:
    """Generate a basic idle motion3.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    motion = {
        "Version": 3,
        "Meta": {
            "Duration": 6.0,
            "Fps": 30.0,
            "Loop": True,
            "CurveCount": 3,
            "TotalSegmentCount": 12,
            "TotalPointCount": 24,
        },
        "Curves": [
            {
                "Target": "Parameter",
                "Id": "ParamAngleX",
                "Segments": [0, 0.0, 0.0, 1, 3.0, 5.0, 1, 6.0, 0.0],
            },
            {
                "Target": "Parameter",
                "Id": "ParamAngleY",
                "Segments": [0, 0.0, 0.0, 1, 2.0, 3.0, 1, 4.0, -2.0, 1, 6.0, 0.0],
            },
            {
                "Target": "Parameter",
                "Id": "ParamBreath",
                "Segments": [0, 0.0, 0.0, 1, 1.5, 1.0, 1, 3.0, 0.0, 1, 4.5, 1.0, 1, 6.0, 0.0],
            },
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(motion, f, ensure_ascii=False, indent=2)
