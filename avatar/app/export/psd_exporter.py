"""Export decomposed parts as a layered PSD file for Cubism Editor import."""

import struct
from pathlib import Path

import numpy as np
from PIL import Image


def export_psd(parts_data, session_dir: Path, output_path: Path, canvas_width: int, canvas_height: int) -> None:
    """Create a PSD file with each part as a named layer.

    Uses a minimal PSD writer since psd-tools is primarily a reader.
    Creates a valid PSD that Cubism Editor and Photoshop can import.
    """
    layers = []
    for part in reversed(parts_data):  # PSD layers: bottom first
        if not part.visible:
            continue
        img_path = session_dir / "parts" / part.image_filename
        if not img_path.exists():
            continue
        img = Image.open(img_path).convert("RGBA")
        layers.append({
            "name": part.label,
            "image": img,
            "x": part.bounds["x"],
            "y": part.bounds["y"],
        })

    _write_psd(output_path, canvas_width, canvas_height, layers)


def _write_psd(path: Path, width: int, height: int, layers: list[dict]) -> None:
    """Write a minimal but valid PSD file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        # --- File Header ---
        f.write(b"8BPS")  # Signature
        f.write(struct.pack(">H", 1))  # Version
        f.write(b"\x00" * 6)  # Reserved
        f.write(struct.pack(">H", 4))  # Channels (RGBA)
        f.write(struct.pack(">I", height))  # Height
        f.write(struct.pack(">I", width))  # Width
        f.write(struct.pack(">H", 8))  # Bits per channel
        f.write(struct.pack(">H", 3))  # Color mode: RGB

        # --- Color Mode Data ---
        f.write(struct.pack(">I", 0))

        # --- Image Resources ---
        f.write(struct.pack(">I", 0))

        # --- Layer and Mask Information ---
        layer_section = _build_layer_section(width, height, layers)
        # PSD spec requires layer section length to be even-padded
        if len(layer_section) % 2 != 0:
            layer_section += b'\x00'
        f.write(struct.pack(">I", len(layer_section)))
        f.write(layer_section)

        # --- Image Data (composite) ---
        f.write(struct.pack(">H", 0))  # Raw compression
        composite = _create_composite(width, height, layers)
        for channel in range(4):  # R, G, B, A
            f.write(composite[:, :, channel].tobytes())


def _build_layer_section(width: int, height: int, layers: list[dict]) -> bytes:
    """Build the layer and mask information section."""
    data = bytearray()

    layer_info = _build_layer_info(width, height, layers)
    data += struct.pack(">I", len(layer_info))
    data += layer_info

    return bytes(data)


def _build_layer_info(width: int, height: int, layers: list[dict]) -> bytes:
    """Build layer info block."""
    data = bytearray()

    data += struct.pack(">h", len(layers))

    channel_data_list = []

    for layer in layers:
        img = layer["image"]
        lx = layer["x"]
        ly = layer["y"]
        lw, lh = img.size

        top = ly
        left = lx
        bottom = ly + lh
        right = lx + lw

        data += struct.pack(">i", top)
        data += struct.pack(">i", left)
        data += struct.pack(">i", bottom)
        data += struct.pack(">i", right)

        data += struct.pack(">H", 4)  # Number of channels

        arr = np.array(img)
        channel_bytes = []
        for ch_id in [-1, 0, 1, 2]:  # Alpha, R, G, B
            if ch_id == -1:
                ch_data = arr[:, :, 3].tobytes()
            else:
                ch_data = arr[:, :, ch_id].tobytes()
            raw_data = struct.pack(">H", 0) + ch_data  # Raw compression
            channel_bytes.append((ch_id, raw_data))

        for ch_id, ch_raw in channel_bytes:
            data += struct.pack(">h", ch_id)
            data += struct.pack(">I", len(ch_raw))

        channel_data_list.append(channel_bytes)

        data += b"8BIM"  # Blend mode signature
        data += b"norm"  # Blend mode: normal
        data += struct.pack(">B", 255)  # Opacity
        data += struct.pack(">B", 0)  # Clipping
        data += struct.pack(">B", 0)  # Flags
        data += struct.pack(">B", 0)  # Filler

        # PSD Pascal string uses MacRoman encoding; use ASCII-safe label
        name_bytes = layer["name"].encode("ascii", errors="replace")
        if len(name_bytes) > 255:
            name_bytes = name_bytes[:255]
        padded_name_len = len(name_bytes) + 1
        padded_name_len = ((padded_name_len + 3) // 4) * 4
        extra_data = struct.pack(">B", len(name_bytes)) + name_bytes
        extra_data += b"\x00" * (padded_name_len - len(extra_data))

        layer_mask_data = struct.pack(">I", 0)
        blending_ranges = struct.pack(">I", 0)

        extra_block = layer_mask_data + blending_ranges + extra_data
        data += struct.pack(">I", len(extra_block))
        data += extra_block

    for channel_bytes in channel_data_list:
        for _, ch_raw in channel_bytes:
            data += ch_raw

    return bytes(data)


def _create_composite(width: int, height: int, layers: list[dict]) -> np.ndarray:
    """Create a flattened composite image from all layers."""
    composite = np.zeros((height, width, 4), dtype=np.uint8)

    for layer in layers:
        img = np.array(layer["image"])
        lx = layer["x"]
        ly = layer["y"]
        lh, lw = img.shape[:2]

        y1 = max(0, ly)
        x1 = max(0, lx)
        y2 = min(height, ly + lh)
        x2 = min(width, lx + lw)

        sy1 = y1 - ly
        sx1 = x1 - lx
        sy2 = sy1 + (y2 - y1)
        sx2 = sx1 + (x2 - x1)

        if y2 <= y1 or x2 <= x1:
            continue

        src = img[sy1:sy2, sx1:sx2]
        dst = composite[y1:y2, x1:x2]

        src_alpha = src[:, :, 3:4].astype(np.float32) / 255.0
        dst_alpha = dst[:, :, 3:4].astype(np.float32) / 255.0

        out_alpha = src_alpha + dst_alpha * (1 - src_alpha)
        mask = out_alpha > 0
        if mask.any():
            for c in range(3):
                dst[:, :, c:c+1] = np.where(
                    mask,
                    ((src[:, :, c:c+1].astype(np.float32) * src_alpha +
                      dst[:, :, c:c+1].astype(np.float32) * dst_alpha * (1 - src_alpha)) /
                     np.maximum(out_alpha, 1e-6)).astype(np.uint8),
                    dst[:, :, c:c+1],
                )
            dst[:, :, 3:4] = (out_alpha * 255).astype(np.uint8)

    return composite
