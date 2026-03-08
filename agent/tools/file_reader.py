"""Read from the input/ workspace directories."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("social-agent")


class FileReader:
    def __init__(self, workspace_root: str):
        self.workspace = Path(workspace_root)
        self.input_dir = self.workspace / "input"
        self.raw_thoughts_dir = self.input_dir / "raw-thoughts"
        self.style_ref_dir = self.input_dir / "style-reference"

    def read_raw_thought(self, filename: str) -> str:
        """Read a single raw thought file by name."""
        path = self.raw_thoughts_dir / filename
        return path.read_text(encoding="utf-8")

    def list_raw_thoughts(self) -> list[str]:
        """List all raw thought filenames, sorted alphabetically."""
        if not self.raw_thoughts_dir.exists():
            return []
        return sorted([f.name for f in self.raw_thoughts_dir.glob("*.md")])

    def list_unprocessed_thoughts(self, output_dir: Path) -> list[str]:
        """Return raw thoughts that don't yet have a corresponding output folder."""
        all_thoughts = self.list_raw_thoughts()
        processed = set()
        if output_dir.exists():
            processed = {d.name for d in output_dir.iterdir() if d.is_dir()}
        return [t for t in all_thoughts if t.replace(".md", "") not in processed]

    def read_style_reference(self, platform: str) -> Optional[str]:
        """Read platform-specific style reference samples."""
        path = self.style_ref_dir / f"{platform}-samples.md"
        if not path.exists():
            logger.warning(f"Style reference not found: {path}")
            return None
        return path.read_text(encoding="utf-8")
