from dataclasses import dataclass


@dataclass
class PartLabel:
    id: str
    name_ja: str
    depth_order: int  # lower = further back
    category: str = ""       # "hair", "face", "body", "clothing", "accessory", etc.
    gender: str = "unisex"   # "male", "female", "unisex"


# Categories
C_HAIR = "hair"
C_BODY = "body"
C_FACE = "face"
C_TOPS = "tops"
C_BOTTOMS_SKIRT = "bottoms_skirt"
C_BOTTOMS_PANTS = "bottoms_pants"
C_ONE_PIECE = "one_piece"
C_OUTER = "outer"
C_UNDERWEAR_TOP = "underwear_top"
C_UNDERWEAR_BOTTOM = "underwear_bottom"
C_SOCKS = "socks"
C_SHOES = "shoes"
C_HAT = "hat"
C_COLLAR = "collar"
C_GLOVES = "gloves"
C_SLEEVE = "sleeve"
C_ACCESSORY = "accessory"
C_COSTUME = "costume"       # full costume composite
C_LIMB = "limb"

# Gender
G_MALE = "male"
G_FEMALE = "female"
G_UNISEX = "unisex"

# Category metadata (for UI display)
CATEGORY_INFO = {
    C_HAIR: {"name_ja": "髪", "icon": "💇"},
    C_BODY: {"name_ja": "体", "icon": "🧍"},
    C_FACE: {"name_ja": "顔", "icon": "😊"},
    C_TOPS: {"name_ja": "トップス", "icon": "👕"},
    C_BOTTOMS_SKIRT: {"name_ja": "スカート", "icon": "👗"},
    C_BOTTOMS_PANTS: {"name_ja": "パンツ", "icon": "👖"},
    C_ONE_PIECE: {"name_ja": "ワンピース", "icon": "👗"},
    C_OUTER: {"name_ja": "アウター", "icon": "🧥"},
    C_UNDERWEAR_TOP: {"name_ja": "下着（上）", "icon": "👙"},
    C_UNDERWEAR_BOTTOM: {"name_ja": "下着（下）", "icon": "🩲"},
    C_SOCKS: {"name_ja": "靴下・ストッキング", "icon": "🧦"},
    C_SHOES: {"name_ja": "靴", "icon": "👟"},
    C_HAT: {"name_ja": "帽子・頭飾り", "icon": "🎩"},
    C_COLLAR: {"name_ja": "襟・ネックウェア", "icon": "👔"},
    C_GLOVES: {"name_ja": "手袋", "icon": "🧤"},
    C_SLEEVE: {"name_ja": "袖", "icon": "💪"},
    C_ACCESSORY: {"name_ja": "アクセサリー", "icon": "💍"},
    C_COSTUME: {"name_ja": "衣装（全体）", "icon": "👘"},
    C_LIMB: {"name_ja": "四肢", "icon": "🦵"},
}

GENDER_INFO = {
    G_MALE: {"name_ja": "男性用", "icon": "♂"},
    G_FEMALE: {"name_ja": "女性用", "icon": "♀"},
    G_UNISEX: {"name_ja": "男女共用", "icon": "⚥"},
}


PART_DEFINITIONS = [
    # Hair
    PartLabel("hair_back", "後ろ髪", 0, C_HAIR, G_UNISEX),
    PartLabel("hair_front", "前髪", 18, C_HAIR, G_UNISEX),
    PartLabel("hair_side_left", "左横髪", 19, C_HAIR, G_UNISEX),
    PartLabel("hair_side_right", "右横髪", 20, C_HAIR, G_UNISEX),
    # Body
    PartLabel("body_skin", "素体（肌）", 1, C_BODY, G_UNISEX),
    PartLabel("body", "体", 1, C_BODY, G_UNISEX),
    PartLabel("neck", "首", 6, C_BODY, G_UNISEX),
    # Clothing - general (gender assigned dynamically by classifier)
    PartLabel("underwear", "下着", 2, C_UNDERWEAR_BOTTOM, G_UNISEX),
    PartLabel("outerwear_lower", "下半身衣装", 3, C_BOTTOMS_PANTS, G_UNISEX),
    PartLabel("outerwear_upper", "上半身衣装", 4, C_TOPS, G_UNISEX),
    # Limbs - arms
    PartLabel("upper_arm_left", "左上腕", 5, C_LIMB, G_UNISEX),
    PartLabel("forearm_left", "左前腕", 5, C_LIMB, G_UNISEX),
    PartLabel("hand_left", "左手", 5, C_LIMB, G_UNISEX),
    PartLabel("fingers_left", "左手指", 5, C_LIMB, G_UNISEX),
    PartLabel("arm_left", "左腕", 5, C_LIMB, G_UNISEX),
    PartLabel("upper_arm_right", "右上腕", 6, C_LIMB, G_UNISEX),
    PartLabel("forearm_right", "右前腕", 6, C_LIMB, G_UNISEX),
    PartLabel("hand_right", "右手", 6, C_LIMB, G_UNISEX),
    PartLabel("fingers_right", "右手指", 6, C_LIMB, G_UNISEX),
    PartLabel("arm_right", "右腕", 6, C_LIMB, G_UNISEX),
    # Limbs - legs
    PartLabel("thigh_left", "左太腿", 3, C_LIMB, G_UNISEX),
    PartLabel("shin_left", "左膝下", 3, C_LIMB, G_UNISEX),
    PartLabel("foot_left", "左足", 3, C_LIMB, G_UNISEX),
    PartLabel("leg_left", "左脚", 3, C_LIMB, G_UNISEX),
    PartLabel("thigh_right", "右太腿", 3, C_LIMB, G_UNISEX),
    PartLabel("shin_right", "右膝下", 3, C_LIMB, G_UNISEX),
    PartLabel("foot_right", "右足", 3, C_LIMB, G_UNISEX),
    PartLabel("leg_right", "右脚", 3, C_LIMB, G_UNISEX),
    # Face
    PartLabel("face", "顔", 7, C_FACE, G_UNISEX),
    PartLabel("ear_left", "左耳", 8, C_FACE, G_UNISEX),
    PartLabel("ear_right", "右耳", 9, C_FACE, G_UNISEX),
    PartLabel("eye_white_left", "左白目", 10, C_FACE, G_UNISEX),
    PartLabel("eye_white_right", "右白目", 11, C_FACE, G_UNISEX),
    PartLabel("eye_left", "左目", 10, C_FACE, G_UNISEX),
    PartLabel("eye_right", "右目", 11, C_FACE, G_UNISEX),
    PartLabel("iris_left", "左瞳", 12, C_FACE, G_UNISEX),
    PartLabel("iris_right", "右瞳", 13, C_FACE, G_UNISEX),
    PartLabel("eyebrow_left", "左眉", 14, C_FACE, G_UNISEX),
    PartLabel("eyebrow_right", "右眉", 15, C_FACE, G_UNISEX),
    PartLabel("nose", "鼻", 16, C_FACE, G_UNISEX),
    PartLabel("mouth", "口", 17, C_FACE, G_UNISEX),
    PartLabel("accessory", "アクセサリー", 21, C_ACCESSORY, G_UNISEX),
    # Costume-only mode labels
    PartLabel("collar", "襟・ネックウェア", 5, C_COLLAR, G_UNISEX),
    PartLabel("sleeve_left", "左袖", 5, C_SLEEVE, G_UNISEX),
    PartLabel("sleeve_right", "右袖", 6, C_SLEEVE, G_UNISEX),
    PartLabel("legwear", "レッグウェア", 3, C_SOCKS, G_UNISEX),
    PartLabel("footwear", "靴", 2, C_SHOES, G_UNISEX),
    PartLabel("headwear", "帽子・頭飾り", 22, C_HAT, G_UNISEX),
    PartLabel("costume_full", "衣装（全体）", 4, C_COSTUME, G_UNISEX),
]

LABEL_MAP = {p.id: p for p in PART_DEFINITIONS}


def get_label_ja(label_id: str) -> str:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).name_ja


def get_depth_order(label_id: str) -> int:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).depth_order


def get_category(label_id: str) -> str:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).category


def get_default_gender(label_id: str) -> str:
    return LABEL_MAP.get(label_id, PartLabel(label_id, label_id, 99)).gender
