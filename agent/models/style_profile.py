"""Style profile schemas for platform-specific writing analysis."""

from pydantic import BaseModel


class PlatformStyle(BaseModel):
    tone: str
    avg_length: str
    hook_pattern: str
    emoji_usage: str
    hashtag_style: str
    cta_style: str
    vocabulary: str
    formatting: str


class StyleProfile(BaseModel):
    twitter: PlatformStyle
    linkedin: PlatformStyle
