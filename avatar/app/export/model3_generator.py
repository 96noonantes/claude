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


def generate_physics3_json(output_path: Path, session: SessionData | None = None) -> None:
    """Generate physics3.json with dynamic physics for hair, clothing, and accessories.

    Detects which parts exist and generates appropriate pendulum physics:
    - Hair (front, side, back): light, responsive sway
    - Skirt/lower outerwear: heavier, gravity-driven swing
    - Upper outerwear loose parts: medium sway
    - Accessories: light, fast oscillation
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    settings = []
    dictionary = []
    setting_id = 0

    visible_labels = set()
    if session:
        visible_labels = {p.label for p in session.parts if p.visible}

    # --- Hair physics ---
    hair_configs = [
        ("hair_front", "前髪揺れ", "ParamHairFront", 0.95, 0.8, 5.0, 3.0),
        ("hair_back", "後ろ髪揺れ", "ParamHairBack", 0.90, 0.6, 8.0, 4.0),
        ("hair_side_left", "左横髪揺れ", "ParamHairSideL", 0.92, 0.7, 6.0, 3.5),
        ("hair_side_right", "右横髪揺れ", "ParamHairSideR", 0.92, 0.7, 6.0, 3.5),
    ]

    for label, name, param_id, mobility, delay, length, radius in hair_configs:
        if not visible_labels or label in visible_labels:
            setting_id += 1
            sid = f"PhysicsSetting{setting_id}"
            dictionary.append({"Id": sid, "Name": name})
            settings.append(_make_pendulum_setting(
                sid, param_id,
                input_id="ParamAngleX", input_weight=100,
                mobility=mobility, delay=delay,
                length=length, radius=radius,
                scale=0.5,
            ))

    # --- Clothing physics (skirt, loose outerwear) ---
    # Skirt / lower outerwear: heavy pendulum, gravity-driven
    if not visible_labels or "outerwear_lower" in visible_labels:
        setting_id += 1
        sid = f"PhysicsSetting{setting_id}"
        dictionary.append({"Id": sid, "Name": "スカート揺れ（中央）"})
        settings.append(_make_pendulum_setting(
            sid, "ParamSkirtCenter",
            input_id="ParamBodyAngleX", input_weight=100,
            mobility=0.85, delay=0.5,
            length=10.0, radius=5.0,
            scale=0.6, acceleration=2.0,
            # Multi-vertex chain for more natural cloth movement
            extra_vertices=[
                {"Position": {"X": 0.0, "Y": 5.0}, "Mobility": 0.88, "Delay": 0.6, "Acceleration": 1.8, "Radius": 4.0},
                {"Position": {"X": 0.0, "Y": 10.0}, "Mobility": 0.82, "Delay": 0.4, "Acceleration": 2.0, "Radius": 5.0},
            ],
        ))

        # Left/right skirt panels for more dynamic movement
        for side_name, side_ja, param_suffix, reflect in [
            ("left", "左", "L", False), ("right", "右", "R", True),
        ]:
            setting_id += 1
            sid = f"PhysicsSetting{setting_id}"
            dictionary.append({"Id": sid, "Name": f"スカート揺れ（{side_ja}）"})
            settings.append(_make_pendulum_setting(
                sid, f"ParamSkirt{param_suffix}",
                input_id="ParamBodyAngleX", input_weight=80,
                mobility=0.87, delay=0.55,
                length=9.0, radius=4.5,
                scale=0.5, acceleration=1.8,
                reflect=reflect,
                extra_vertices=[
                    {"Position": {"X": 0.0, "Y": 9.0}, "Mobility": 0.83, "Delay": 0.45, "Acceleration": 1.9, "Radius": 4.5},
                ],
            ))

    # Upper outerwear loose parts (jacket flaps, ribbons, collar, etc.)
    if not visible_labels or "outerwear_upper" in visible_labels:
        setting_id += 1
        sid = f"PhysicsSetting{setting_id}"
        dictionary.append({"Id": sid, "Name": "上着揺れ"})
        settings.append(_make_pendulum_setting(
            sid, "ParamOuterwearUpper",
            input_id="ParamAngleX", input_weight=60,
            mobility=0.9, delay=0.7,
            length=4.0, radius=2.5,
            scale=0.3,
        ))

    # --- Accessory physics ---
    if not visible_labels or "accessory" in visible_labels:
        setting_id += 1
        sid = f"PhysicsSetting{setting_id}"
        dictionary.append({"Id": sid, "Name": "アクセサリー揺れ"})
        settings.append(_make_pendulum_setting(
            sid, "ParamAccessory",
            input_id="ParamAngleX", input_weight=50,
            mobility=0.97, delay=0.9,
            length=3.0, radius=2.0,
            scale=0.4,
        ))

    # Count totals
    total_input = sum(len(s["Input"]) for s in settings)
    total_output = sum(len(s["Output"]) for s in settings)
    total_vertices = sum(len(s["Vertices"]) for s in settings)

    physics = {
        "Version": 3,
        "Meta": {
            "PhysicsSettingCount": len(settings),
            "TotalInputCount": total_input,
            "TotalOutputCount": total_output,
            "VertexCount": total_vertices,
            "Fps": 30.0,
            "EffectiveForces": {
                "Gravity": {"X": 0.0, "Y": -1.0},
                "Wind": {"X": 0.0, "Y": 0.0},
            },
            "PhysicsDictionary": dictionary,
        },
        "PhysicsSettings": settings,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(physics, f, ensure_ascii=False, indent=2)


def _make_pendulum_setting(
    setting_id: str,
    output_param: str,
    input_id: str = "ParamAngleX",
    input_weight: int = 100,
    mobility: float = 0.95,
    delay: float = 0.8,
    length: float = 5.0,
    radius: float = 3.0,
    scale: float = 0.5,
    acceleration: float = 1.5,
    reflect: bool = False,
    extra_vertices: list | None = None,
) -> dict:
    """Create a single pendulum physics setting."""
    vertices = [
        {"Position": {"X": 0.0, "Y": 0.0}, "Mobility": 1.0, "Delay": 1.0, "Acceleration": 1.0, "Radius": 0.0},
        {"Position": {"X": 0.0, "Y": length}, "Mobility": mobility, "Delay": delay, "Acceleration": acceleration, "Radius": radius},
    ]
    if extra_vertices:
        vertices.extend(extra_vertices)

    return {
        "Id": setting_id,
        "Input": [{
            "Source": {"Target": "Parameter", "Id": input_id},
            "Weight": input_weight,
            "Type": "X",
            "Reflect": reflect,
        }],
        "Output": [{
            "Destination": {"Target": "Parameter", "Id": output_param},
            "VertexIndex": 1,
            "Scale": scale,
            "Weight": 100,
            "Type": "Angle",
            "Reflect": reflect,
        }],
        "Vertices": vertices,
        "Normalization": {
            "Position": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0},
            "Angle": {"Minimum": -10.0, "Default": 0.0, "Maximum": 10.0},
        },
    }


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
