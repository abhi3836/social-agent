"""Draft output model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Draft(BaseModel):
    platform: str  # "twitter" or "linkedin"
    content: str
    draft_type: str  # "single" or "thread"
    source_file: str
    generated_at: datetime
    image_suggestion: Optional[str] = None
    posted_ids: list[str] = []
