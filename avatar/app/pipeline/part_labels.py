from dataclasses import dataclass


@dataclass
class PartLabel:
    id: str
    name_ja: str
    depth_order: int  # lower = further back


PART_DEFINITIONS = [
    PartLabel("hair_back", "後ろ髪", 0),
    PartLabel("body", "体", 1),
    PartLabel("arm_left", "左腕", 2),
    PartLabel("arm_right", "右腕", 3),
    PartLabel("face", "顔", 4),
    PartLabel("ear_left", "左耳", 5),
    PartLabel("ear_right", "右耳", 6),
    PartLabel("eye_white_left", "左白目", 7),
    PartLabel("eye_white_right", "右白目", 8),
    PartLabel("iris_left", "左瞳", 9),
    PartLabel("iris_right", "右瞳", 10),
    PartLabel("eyebrow_left", "左眉", 11),
    PartLabel("eyebrow_right", "右眉", 12),
    PartLabel("nose", "鼻", 13),
    PartLabel("mouth", "口", 14),
    PartLabel("hair_front", "前髪", 15),
    PartLabel("hair_side_left", "左横髪", 16),
    PartLabel("hair_side_right", "右横髪", 17),
    PartLabel("accessory", "アクセサリー", 18),
]

LABEL_MAP = {p.id: p for p in PART_DEFINITIONS}


def get_label_ja(label_id: str) -> str:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).name_ja


def get_depth_order(label_id: str) -> int:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).depth_order
