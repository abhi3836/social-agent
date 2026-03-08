"""Write drafts, images, metadata, suggestions, and errors to output/."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("social-agent")


class FileWriter:
    def __init__(self, workspace_root: str):
        self.workspace = Path(workspace_root)
        self.drafts_dir = self.workspace / "output" / "drafts"
        self.suggestions_dir = self.workspace / "output" / "suggestions"

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def write_draft(self, source_filename: str, platform: str, content: str) -> Path:
        """Write a platform-specific draft markdown file."""
        slug = source_filename.replace(".md", "")
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / f"{platform}-draft.md"
        out_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote draft: {out_path}")
        return out_path

    def write_image(self, source_filename: str, platform: str, image_bytes: bytes) -> Path:
        """Write a generated image file."""
        slug = source_filename.replace(".md", "")
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / f"image-{platform}.png"
        out_path.write_bytes(image_bytes)
        logger.info(f"Wrote image: {out_path}")
        return out_path

    def write_metadata(self, source_filename: str, metadata: dict) -> Path:
        """Write metadata.json for a draft folder."""
        slug = source_filename.replace(".md", "")
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / "metadata.json"
        out_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return out_path

    def write_suggestions(self, content: str) -> Path:
        """Write the suggestions markdown file."""
        self._ensure_dir(self.suggestions_dir)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = self.suggestions_dir / f"{date_str}-suggestions.md"
        out_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote suggestions: {out_path}")
        return out_path

    def write_error(self, source_filename: str, error_msg: str) -> Path:
        """Write an error log in the draft folder."""
        slug = source_filename.replace(".md", "")
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / "error.log"
        out_path.write_text(error_msg, encoding="utf-8")
        logger.warning(f"Wrote error log: {out_path}")
        return out_path
