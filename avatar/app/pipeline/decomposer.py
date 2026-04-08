"""Main decomposition pipeline: combines background removal, face detection, and region segmentation."""

from pathlib import Path

from app.models.session import PartData
from app.pipeline.preprocessing import load_and_normalize, remove_background
from app.pipeline.face_detector import detect_anime_face
from app.pipeline.region_segmenter import segment_parts


def run_decomposition(image_path: Path, output_dir: Path) -> list[PartData]:
    """Run the full decomposition pipeline on a character image.

    Steps:
    1. Load and normalize the image
    2. Remove background using rembg
    3. Detect anime face landmarks
    4. Segment into parts based on landmarks
    5. Save individual part images

    Returns list of PartData with detected parts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    image_rgba = load_and_normalize(image_path)

    no_bg = remove_background(image_rgba)

    landmarks = detect_anime_face(no_bg)
    if landmarks is None:
        raise ValueError(
            "キャラクターの顔を検出できませんでした。"
            "正面を向いたアニメキャラクターの画像を使用してください。"
        )

    parts = segment_parts(image_rgba, no_bg, landmarks, output_dir)

    if not parts:
        raise ValueError("パーツの分解に失敗しました。画像を確認してください。")

    return parts
