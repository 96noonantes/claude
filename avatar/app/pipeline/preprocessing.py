"""Image preprocessing with optimized background removal.

Improvements:
- Uses isnet-anime model explicitly for anime character images
- Adaptive alpha matting thresholds based on histogram analysis
- Session caching to avoid reloading the model
- Fallback to birefnet-general if isnet-anime fails
"""

import threading

import numpy as np
from PIL import Image

from app.config import TARGET_IMAGE_DIMENSION

_rembg_lock = threading.Lock()
_rembg_session = None
_rembg_model_name = None


def _get_rembg_session(model_name: str = "isnet-anime"):
    """Get or create a cached rembg session (thread-safe)."""
    global _rembg_session, _rembg_model_name
    with _rembg_lock:
        if _rembg_session is None or _rembg_model_name != model_name:
            from rembg import new_session
            _rembg_session = new_session(model_name)
            _rembg_model_name = model_name
        return _rembg_session


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
    """Remove background using rembg with isnet-anime model.

    Uses adaptive alpha matting thresholds and falls back to
    birefnet-general if the primary model produces poor results.
    """
    from rembg import remove

    img = Image.fromarray(image_rgba)
    session = _get_rembg_session("isnet-anime")

    # Compute adaptive alpha matting thresholds
    fg_threshold, bg_threshold = _compute_adaptive_thresholds(image_rgba)

    result = remove(
        img,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=fg_threshold,
        alpha_matting_background_threshold=bg_threshold,
        post_process_mask=True,
    )
    result_arr = np.array(result)

    # Check if result is reasonable (at least 5% of pixels are foreground)
    fg_ratio = np.sum(result_arr[:, :, 3] > 128) / (result_arr.shape[0] * result_arr.shape[1])
    if fg_ratio < 0.05:
        # Retry with birefnet-general
        fallback_session = _get_rembg_session("birefnet-general")
        result = remove(
            img,
            session=fallback_session,
            alpha_matting=True,
            alpha_matting_foreground_threshold=fg_threshold,
            alpha_matting_background_threshold=bg_threshold,
            post_process_mask=True,
        )
        result_arr = np.array(result)
        # Restore primary session for next call
        _get_rembg_session("isnet-anime")

    return result_arr


def _compute_adaptive_thresholds(image_rgba: np.ndarray) -> tuple[int, int]:
    """Compute adaptive alpha matting thresholds based on image characteristics."""
    # Analyze the brightness distribution
    gray = np.mean(image_rgba[:, :, :3], axis=2)
    mean_brightness = np.mean(gray)

    # Lighter images need higher foreground threshold
    # Darker images need lower background threshold
    if mean_brightness > 180:
        fg_threshold = 250
        bg_threshold = 15
    elif mean_brightness > 120:
        fg_threshold = 240
        bg_threshold = 12
    else:
        fg_threshold = 230
        bg_threshold = 8

    return fg_threshold, bg_threshold
