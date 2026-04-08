"""Build the final export ZIP package for Cubism Editor."""

import shutil
from pathlib import Path

from app.models.session import SessionData
from app.export.psd_exporter import export_psd
from app.export.model3_generator import (
    generate_model3_json,
    generate_physics3_json,
    generate_motion_files,
    generate_expression_files,
)


def build_export_package(session: SessionData) -> Path:
    """Build a ZIP containing PSD, model3.json, physics, motions, expressions, and part PNGs."""
    export_dir = session.dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    build_dir = export_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

    # Copy part PNGs
    parts_out = build_dir / "parts"
    parts_out.mkdir()
    for part in session.parts:
        if part.visible:
            src = session.parts_dir / part.image_filename
            if src.exists():
                shutil.copy2(src, parts_out / part.image_filename)

    # Generate PSD
    export_psd(
        session.parts,
        session.dir,
        build_dir / "parts.psd",
        session.image_width,
        session.image_height,
    )

    # Generate model3.json + parameters.json
    generate_model3_json(session, build_dir / "model3.json")

    # Generate physics3.json
    generate_physics3_json(build_dir / "physics3.json")

    # Generate motions (idle, blink)
    generate_motion_files(build_dir / "motions")

    # Generate expression presets (happy, sad, angry, surprised, etc.)
    generate_expression_files(build_dir / "expressions")

    # Create ZIP
    zip_path = export_dir / f"live2d_avatar_{session.session_id}"
    shutil.make_archive(str(zip_path), "zip", str(build_dir))

    return Path(f"{zip_path}.zip")
