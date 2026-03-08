"""Output validation helpers for images and raw thoughts."""

from pathlib import Path
from typing import Optional

from PIL import Image

PLATFORM_SPECS = {
    "twitter": {"width": 1200, "height": 675, "max_bytes": 5 * 1024 * 1024},
    "linkedin": {"width": 1200, "height": 627, "max_bytes": 5 * 1024 * 1024},
}


def validate_image(path: Path, platform: str) -> tuple[bool, Optional[str]]:
    """Validate image dimensions and file size for a given platform."""
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        return False, f"Unknown platform: {platform}"
    if not path.exists():
        return False, f"File not found: {path}"

    size_bytes = path.stat().st_size
    if size_bytes > spec["max_bytes"]:
        return False, f"File too large: {size_bytes} bytes (max {spec['max_bytes']})"

    with Image.open(path) as img:
        w, h = img.size
        if w != spec["width"] or h != spec["height"]:
            return (
                False,
                f"Wrong dimensions: {w}x{h} (expected {spec['width']}x{spec['height']})",
            )

    return True, None


def validate_raw_thought(content: str) -> tuple[bool, Optional[str]]:
    """Basic validation that a raw thought file has enough content to process."""
    if not content or len(content.strip()) < 20:
        return False, "Raw thought is too short (minimum 20 characters)"
    return True, None
