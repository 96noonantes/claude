"""Generate Live2D Cubism model3.json, expression presets, and motions.

Generates a complete expression system:
- model3.json: full parameter definitions for eyes, mouth, eyebrows, face angle
- exp3.json: expression presets (happy, sad, angry, surprised, etc.)
- motion3.json: idle, blink, lip-sync, and expression transition motions
"""

import json
from pathlib import Path

from app.models.session import SessionData

# ============================================================
# Live2D Standard Parameter Definitions
# ============================================================

# Eye parameters
EYE_PARAMS = [
    {"Id": "ParamEyeLOpen", "Min": 0.0, "Max": 1.0, "Default": 1.0},
    {"Id": "ParamEyeROpen", "Min": 0.0, "Max": 1.0, "Default": 1.0},
    {"Id": "ParamEyeLSmile", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamEyeRSmile", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamEyeBallX", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamEyeBallY", "Min": -1.0, "Max": 1.0, "Default": 0.0},
]

# Eyebrow parameters
EYEBROW_PARAMS = [
    {"Id": "ParamBrowLY", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowRY", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowLX", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowRX", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowLAngle", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowRAngle", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowLForm", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamBrowRForm", "Min": -1.0, "Max": 1.0, "Default": 0.0},
]

# Mouth parameters
MOUTH_PARAMS = [
    {"Id": "ParamMouthOpenY", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamMouthForm", "Min": -1.0, "Max": 1.0, "Default": 0.0},  # -1=frown, 0=neutral, 1=smile
    {"Id": "ParamMouthSize", "Min": -1.0, "Max": 1.0, "Default": 0.0},
    # Viseme shapes for lip-sync (vowels: A I U E O)
    {"Id": "ParamMouthA", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamMouthI", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamMouthU", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamMouthE", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamMouthO", "Min": 0.0, "Max": 1.0, "Default": 0.0},
]

# Face angle / head tilt parameters
FACE_PARAMS = [
    {"Id": "ParamAngleX", "Min": -30.0, "Max": 30.0, "Default": 0.0},
    {"Id": "ParamAngleY", "Min": -30.0, "Max": 30.0, "Default": 0.0},
    {"Id": "ParamAngleZ", "Min": -30.0, "Max": 30.0, "Default": 0.0},
    {"Id": "ParamBodyAngleX", "Min": -10.0, "Max": 10.0, "Default": 0.0},
    {"Id": "ParamBodyAngleY", "Min": -10.0, "Max": 10.0, "Default": 0.0},
    {"Id": "ParamBodyAngleZ", "Min": -10.0, "Max": 10.0, "Default": 0.0},
    {"Id": "ParamBreath", "Min": 0.0, "Max": 1.0, "Default": 0.0},
]

# Cheek (blush)
EXTRA_PARAMS = [
    {"Id": "ParamCheek", "Min": 0.0, "Max": 1.0, "Default": 0.0},
    {"Id": "ParamTear", "Min": 0.0, "Max": 1.0, "Default": 0.0},
]

ALL_PARAMS = EYE_PARAMS + EYEBROW_PARAMS + MOUTH_PARAMS + FACE_PARAMS + EXTRA_PARAMS

# ============================================================
# Expression Presets
# ============================================================

EXPRESSION_PRESETS = {
    "neutral": {
        "name_ja": "通常",
        "params": {},
    },
    "happy": {
        "name_ja": "喜び",
        "params": {
            "ParamEyeLSmile": 1.0,
            "ParamEyeRSmile": 1.0,
            "ParamEyeLOpen": 0.7,
            "ParamEyeROpen": 0.7,
            "ParamMouthForm": 1.0,
            "ParamMouthOpenY": 0.3,
            "ParamBrowLY": 0.3,
            "ParamBrowRY": 0.3,
        },
    },
    "sad": {
        "name_ja": "悲しみ",
        "params": {
            "ParamEyeLOpen": 0.6,
            "ParamEyeROpen": 0.6,
            "ParamMouthForm": -0.7,
            "ParamBrowLY": -0.5,
            "ParamBrowRY": -0.5,
            "ParamBrowLAngle": -0.6,
            "ParamBrowRAngle": -0.6,
            "ParamTear": 0.5,
        },
    },
    "angry": {
        "name_ja": "怒り",
        "params": {
            "ParamEyeLOpen": 0.9,
            "ParamEyeROpen": 0.9,
            "ParamMouthForm": -0.5,
            "ParamMouthOpenY": 0.2,
            "ParamBrowLY": -0.3,
            "ParamBrowRY": -0.3,
            "ParamBrowLAngle": 0.8,
            "ParamBrowRAngle": 0.8,
        },
    },
    "surprised": {
        "name_ja": "驚き",
        "params": {
            "ParamEyeLOpen": 1.0,
            "ParamEyeROpen": 1.0,
            "ParamMouthOpenY": 0.8,
            "ParamMouthForm": 0.0,
            "ParamMouthO": 0.8,
            "ParamBrowLY": 0.8,
            "ParamBrowRY": 0.8,
        },
    },
    "embarrassed": {
        "name_ja": "照れ",
        "params": {
            "ParamEyeLSmile": 0.6,
            "ParamEyeRSmile": 0.6,
            "ParamEyeLOpen": 0.5,
            "ParamEyeROpen": 0.5,
            "ParamMouthForm": 0.4,
            "ParamCheek": 1.0,
            "ParamBrowLY": 0.2,
            "ParamBrowRY": 0.2,
            "ParamAngleZ": 5.0,
        },
    },
    "wink_left": {
        "name_ja": "ウインク（左）",
        "params": {
            "ParamEyeLOpen": 0.0,
            "ParamEyeROpen": 1.0,
            "ParamEyeLSmile": 0.8,
            "ParamMouthForm": 0.7,
        },
    },
    "wink_right": {
        "name_ja": "ウインク（右）",
        "params": {
            "ParamEyeLOpen": 1.0,
            "ParamEyeROpen": 0.0,
            "ParamEyeRSmile": 0.8,
            "ParamMouthForm": 0.7,
        },
    },
    "sleepy": {
        "name_ja": "眠い",
        "params": {
            "ParamEyeLOpen": 0.2,
            "ParamEyeROpen": 0.2,
            "ParamMouthOpenY": 0.5,
            "ParamMouthForm": 0.0,
            "ParamBrowLY": -0.3,
            "ParamBrowRY": -0.3,
            "ParamAngleY": -5.0,
        },
    },
    "smug": {
        "name_ja": "ドヤ顔",
        "params": {
            "ParamEyeLOpen": 0.6,
            "ParamEyeROpen": 0.6,
            "ParamEyeLSmile": 0.5,
            "ParamEyeRSmile": 0.5,
            "ParamMouthForm": 0.8,
            "ParamBrowLY": 0.2,
            "ParamBrowRY": -0.2,
            "ParamBrowLAngle": 0.3,
            "ParamAngleZ": -3.0,
        },
    },
    "crying": {
        "name_ja": "泣き",
        "params": {
            "ParamEyeLOpen": 0.3,
            "ParamEyeROpen": 0.3,
            "ParamEyeLSmile": 0.4,
            "ParamEyeRSmile": 0.4,
            "ParamMouthForm": -0.8,
            "ParamMouthOpenY": 0.6,
            "ParamBrowLY": -0.7,
            "ParamBrowRY": -0.7,
            "ParamBrowLAngle": -0.8,
            "ParamBrowRAngle": -0.8,
            "ParamTear": 1.0,
        },
    },
}


# ============================================================
# Generators
# ============================================================

def generate_model3_json(session: SessionData, output_path: Path) -> None:
    """Generate model3.json with full expression parameter support."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    visible_parts = [p for p in session.parts if p.visible]

    has_eyes = any("eye" in p.label or "iris" in p.label for p in visible_parts)
    has_mouth = any(p.label == "mouth" for p in visible_parts)
    has_eyebrows = any("eyebrow" in p.label for p in visible_parts)

    # Parameter groups
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

    # Hit areas
    hit_areas = [{"Id": "HitAreaHead", "Name": "Head"}]
    if any("body" in p.label for p in visible_parts):
        hit_areas.append({"Id": "HitAreaBody", "Name": "Body"})

    # Textures
    texture_files = [f"parts/{p.image_filename}" for p in visible_parts]

    # Motion references
    motions = {
        "Idle": [{"File": "motions/idle.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5}],
    }
    if has_eyes:
        motions["Blink"] = [{"File": "motions/blink.motion3.json", "FadeInTime": 0.1, "FadeOutTime": 0.3}]

    # Expression references
    expressions = []
    for expr_id, expr_data in EXPRESSION_PRESETS.items():
        if expr_id == "neutral":
            continue
        expressions.append({"Name": expr_id, "File": f"expressions/{expr_id}.exp3.json"})

    model3 = {
        "Version": 3,
        "FileReferences": {
            "Moc": "",
            "Textures": texture_files,
            "Physics": "physics3.json",
            "Motions": motions,
            "Expressions": expressions,
        },
        "Groups": groups,
        "HitAreas": hit_areas,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(model3, f, ensure_ascii=False, indent=2)

    # Also write a parameters reference file for Cubism Editor setup
    _write_parameters_reference(output_path.parent / "parameters.json")


def _write_parameters_reference(output_path: Path) -> None:
    """Write a reference file listing all parameters for Cubism Editor configuration."""
    params_doc = {
        "_comment": "Live2Dパラメータ一覧（Cubism Editorでのセットアップ用参考資料）",
        "parameters": ALL_PARAMS,
        "expressions": {
            name: {
                "name_ja": data["name_ja"],
                "parameters": data["params"],
            }
            for name, data in EXPRESSION_PRESETS.items()
        },
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(params_doc, f, ensure_ascii=False, indent=2)


def generate_expression_files(output_dir: Path) -> None:
    """Generate exp3.json files for each expression preset."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for expr_id, expr_data in EXPRESSION_PRESETS.items():
        if expr_id == "neutral":
            continue

        exp3 = {
            "Type": "Live2D Expression",
            "Parameters": [],
        }

        for param_id, value in expr_data["params"].items():
            # Find the default value for this parameter
            param_def = next((p for p in ALL_PARAMS if p["Id"] == param_id), None)
            default_val = param_def["Default"] if param_def else 0.0

            # Blend mode: "Add" offsets from default, "Multiply" scales, "Overwrite" replaces
            if param_id.startswith("ParamEyeL") or param_id.startswith("ParamEyeR"):
                blend = "Overwrite"
            elif param_id.startswith("ParamMouth"):
                blend = "Overwrite"
            elif param_id.startswith("ParamBrow"):
                blend = "Add"
            else:
                blend = "Add"

            exp3["Parameters"].append({
                "Id": param_id,
                "Value": value,
                "Blend": blend,
            })

        filepath = output_dir / f"{expr_id}.exp3.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(exp3, f, ensure_ascii=False, indent=2)


def generate_physics3_json(output_path: Path) -> None:
    """Generate physics3.json for hair and accessory physics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    physics = {
        "Version": 3,
        "Meta": {
            "PhysicsSettingCount": 2,
            "TotalInputCount": 2,
            "TotalOutputCount": 2,
            "VertexCount": 4,
            "Fps": 30.0,
            "EffectiveForces": {
                "Gravity": {"X": 0.0, "Y": -1.0},
                "Wind": {"X": 0.0, "Y": 0.0},
            },
            "PhysicsDictionary": [
                {"Id": "PhysicsSetting1", "Name": "前髪揺れ"},
                {"Id": "PhysicsSetting2", "Name": "横髪揺れ"},
            ],
        },
        "PhysicsSettings": [
            {
                "Id": "PhysicsSetting1",
                "Input": [{"Source": {"Target": "Parameter", "Id": "ParamAngleX"}, "Weight": 100, "Type": "X", "Reflect": False}],
                "Output": [{"Destination": {"Target": "Parameter", "Id": "ParamHairFront"}, "VertexIndex": 1, "Scale": 0.5, "Weight": 100, "Type": "Angle", "Reflect": False}],
                "Vertices": [
                    {"Position": {"X": 0.0, "Y": 0.0}, "Mobility": 1.0, "Delay": 1.0, "Acceleration": 1.0, "Radius": 0.0},
                    {"Position": {"X": 0.0, "Y": 5.0}, "Mobility": 0.95, "Delay": 0.8, "Acceleration": 1.5, "Radius": 3.0},
                ],
                "Normalization": {"Position": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0}, "Angle": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0}},
            },
            {
                "Id": "PhysicsSetting2",
                "Input": [{"Source": {"Target": "Parameter", "Id": "ParamAngleX"}, "Weight": 80, "Type": "X", "Reflect": False}],
                "Output": [{"Destination": {"Target": "Parameter", "Id": "ParamHairSide"}, "VertexIndex": 1, "Scale": 0.4, "Weight": 100, "Type": "Angle", "Reflect": False}],
                "Vertices": [
                    {"Position": {"X": 0.0, "Y": 0.0}, "Mobility": 1.0, "Delay": 1.0, "Acceleration": 1.0, "Radius": 0.0},
                    {"Position": {"X": 0.0, "Y": 6.0}, "Mobility": 0.9, "Delay": 0.7, "Acceleration": 1.3, "Radius": 3.5},
                ],
                "Normalization": {"Position": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0}, "Angle": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0}},
            },
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(physics, f, ensure_ascii=False, indent=2)


def generate_motion_files(motions_dir: Path) -> None:
    """Generate all motion3.json files: idle, blink, and lip-sync demo."""
    motions_dir.mkdir(parents=True, exist_ok=True)

    _generate_idle_motion(motions_dir / "idle.motion3.json")
    _generate_blink_motion(motions_dir / "blink.motion3.json")


def _generate_idle_motion(path: Path) -> None:
    """Idle: subtle breathing, gentle head sway, occasional micro-expressions."""
    motion = {
        "Version": 3,
        "Meta": {"Duration": 8.0, "Fps": 30.0, "Loop": True, "CurveCount": 5},
        "Curves": [
            {
                "Target": "Parameter", "Id": "ParamAngleX",
                # Gentle head sway left-right
                "Segments": _make_sine_segments(8.0, amplitude=4.0, period=6.0),
            },
            {
                "Target": "Parameter", "Id": "ParamAngleY",
                # Subtle nod
                "Segments": _make_sine_segments(8.0, amplitude=2.0, period=4.0),
            },
            {
                "Target": "Parameter", "Id": "ParamAngleZ",
                # Slight head tilt
                "Segments": _make_sine_segments(8.0, amplitude=2.0, period=7.0),
            },
            {
                "Target": "Parameter", "Id": "ParamBreath",
                # Breathing cycle
                "Segments": _make_sine_segments(8.0, amplitude=0.5, period=3.5, offset=0.5, min_val=0.0),
            },
            {
                "Target": "Parameter", "Id": "ParamBodyAngleX",
                # Body sway following head
                "Segments": _make_sine_segments(8.0, amplitude=1.5, period=6.0),
            },
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(motion, f, ensure_ascii=False, indent=2)


def _generate_blink_motion(path: Path) -> None:
    """Blink: quick eye close/open cycle for both eyes."""
    # Blink lasts ~0.15s close + 0.15s open = 0.3s total
    motion = {
        "Version": 3,
        "Meta": {"Duration": 0.4, "Fps": 30.0, "Loop": False, "CurveCount": 2},
        "Curves": [
            {
                "Target": "Parameter", "Id": "ParamEyeLOpen",
                # Linear: 1→0 (close), then 0→1 (open)
                "Segments": [0, 0.0, 1.0, 0, 0.05, 1.0, 1, 0.15, 0.0, 1, 0.2, 0.0, 1, 0.35, 1.0, 0, 0.4, 1.0],
            },
            {
                "Target": "Parameter", "Id": "ParamEyeROpen",
                "Segments": [0, 0.0, 1.0, 0, 0.05, 1.0, 1, 0.15, 0.0, 1, 0.2, 0.0, 1, 0.35, 1.0, 0, 0.4, 1.0],
            },
        ],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(motion, f, ensure_ascii=False, indent=2)


def _make_sine_segments(duration: float, amplitude: float, period: float,
                         offset: float = 0.0, min_val: float = -999.0,
                         steps: int = 16) -> list:
    """Generate Bezier curve segments approximating a sine wave.

    Returns CubismSpecs motion segment format:
    [type, time, value, type, time, value, ...]
    type 0 = linear, type 1 = bezier
    """
    import math
    segments = []
    for i in range(steps + 1):
        t = (i / steps) * duration
        val = offset + amplitude * math.sin(2 * math.pi * t / period)
        if min_val > -999:
            val = max(min_val, val)

        if i == 0:
            segments.extend([0, t, val])
        else:
            segments.extend([1, t, val])

    return segments
