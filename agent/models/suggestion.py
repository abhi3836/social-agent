"""Suggestion output models."""

from pydantic import BaseModel


class PostSuggestion(BaseModel):
    topic: str
    why_now: str
    platforms: list[str]
    outline: str
    score: float


class SuggestionSet(BaseModel):
    themes: list[str]
    suggestions: list[PostSuggestion]
    generated_at: str
