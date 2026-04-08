import numpy as np
from PIL import Image

from app.config import TARGET_IMAGE_DIMENSION


def load_and_normalize(image_path) -> np.ndarray:
    """Load image and convert to RGBA numpy array, resizing if needed."""
    img = Image.open(image_path)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    if max(w, h) > TARGET_IMAGE_DIMENSION:
        scale = TARGET_IMAGE_DIMENSION / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    return np.array(img)


def remove_background(image_rgba: np.ndarray) -> np.ndarray:
    """Remove background using rembg with isnet-anime model."""
    from rembg import remove

    img = Image.fromarray(image_rgba)
    result = remove(
        img,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
    )
    return np.array(result)
