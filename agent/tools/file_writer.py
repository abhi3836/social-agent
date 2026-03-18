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
        self.archive_dir = self.workspace / "input" / "archive"

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(source_filename: str) -> str:
        return Path(source_filename).stem

    def write_draft(self, source_filename: str, platform: str, content: str) -> Path:
        """Write a platform-specific draft markdown file."""
        slug = self._slug(source_filename)
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / f"{platform}-draft.md"
        out_path.write_text(content, encoding="utf-8")
        logger.info(f"Wrote draft: {out_path}")
        return out_path

    def write_image(self, source_filename: str, platform: str, image_bytes: bytes) -> Path:
        """Write a generated image file."""
        slug = self._slug(source_filename)
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / f"image-{platform}.png"
        out_path.write_bytes(image_bytes)
        logger.info(f"Wrote image: {out_path}")
        return out_path

    def write_metadata(self, source_filename: str, metadata: dict) -> Path:
        """Write metadata.json for a draft folder."""
        slug = self._slug(source_filename)
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

    def archive_raw_thought(self, source_filename: str) -> Path:
        """Move a processed raw thought to input/archive/."""
        self._ensure_dir(self.archive_dir)
        src = self.workspace / "input" / "raw-thoughts" / source_filename
        dest = self.archive_dir / source_filename
        src.rename(dest)
        logger.info(f"Archived: {source_filename} → input/archive/")
        return dest

    def write_error(self, source_filename: str, error_msg: str) -> Path:
        """Write an error log in the draft folder."""
        slug = self._slug(source_filename)
        draft_dir = self.drafts_dir / slug
        self._ensure_dir(draft_dir)
        out_path = draft_dir / "error.log"
        out_path.write_text(error_msg, encoding="utf-8")
        logger.warning(f"Wrote error log: {out_path}")
        return out_path
