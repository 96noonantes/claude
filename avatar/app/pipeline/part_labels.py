from dataclasses import dataclass


@dataclass
class PartLabel:
    id: str
    name_ja: str
    depth_order: int  # lower = further back


PART_DEFINITIONS = [
    PartLabel("hair_back", "後ろ髪", 0),
    # Body layers (back to front: skin → underwear → outerwear)
    PartLabel("body_skin", "素体（肌）", 1),
    PartLabel("body", "体", 1),             # fallback when clothing separation fails
    PartLabel("underwear", "下着", 2),
    PartLabel("outerwear_lower", "下半身衣装", 3),
    PartLabel("outerwear_upper", "上半身衣装", 4),
    # Left arm segments (shoulder → fingertips)
    PartLabel("upper_arm_left", "左上腕", 5),
    PartLabel("forearm_left", "左前腕", 5),
    PartLabel("hand_left", "左手", 5),
    PartLabel("fingers_left", "左手指", 5),
    PartLabel("arm_left", "左腕", 5),       # fallback when segmentation fails
    # Right arm segments
    PartLabel("upper_arm_right", "右上腕", 6),
    PartLabel("forearm_right", "右前腕", 6),
    PartLabel("hand_right", "右手", 6),
    PartLabel("fingers_right", "右手指", 6),
    PartLabel("arm_right", "右腕", 6),      # fallback when segmentation fails
    # Left leg segments (thigh → toes)
    PartLabel("thigh_left", "左太腿", 3),
    PartLabel("shin_left", "左膝下", 3),
    PartLabel("foot_left", "左足", 3),
    PartLabel("leg_left", "左脚", 3),       # fallback
    # Right leg segments
    PartLabel("thigh_right", "右太腿", 3),
    PartLabel("shin_right", "右膝下", 3),
    PartLabel("foot_right", "右足", 3),
    PartLabel("leg_right", "右脚", 3),      # fallback
    # Face
    PartLabel("face", "顔", 7),
    PartLabel("neck", "首", 6),
    PartLabel("ear_left", "左耳", 8),
    PartLabel("ear_right", "右耳", 9),
    PartLabel("eye_white_left", "左白目", 10),
    PartLabel("eye_white_right", "右白目", 11),
    PartLabel("eye_left", "左目", 10),
    PartLabel("eye_right", "右目", 11),
    PartLabel("iris_left", "左瞳", 12),
    PartLabel("iris_right", "右瞳", 13),
    PartLabel("eyebrow_left", "左眉", 14),
    PartLabel("eyebrow_right", "右眉", 15),
    PartLabel("nose", "鼻", 16),
    PartLabel("mouth", "口", 17),
    PartLabel("hair_front", "前髪", 18),
    PartLabel("hair_side_left", "左横髪", 19),
    PartLabel("hair_side_right", "右横髪", 20),
    PartLabel("accessory", "アクセサリー", 21),
]

LABEL_MAP = {p.id: p for p in PART_DEFINITIONS}


def get_label_ja(label_id: str) -> str:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).name_ja


def get_depth_order(label_id: str) -> int:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).depth_order
