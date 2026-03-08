"""Tests for Pydantic models."""

from datetime import datetime, timezone

from models.draft import Draft
from models.style_profile import PlatformStyle, StyleProfile
from models.suggestion import PostSuggestion, SuggestionSet


def test_platform_style_creation():
    style = PlatformStyle(
        tone="direct",
        avg_length="180 chars",
        hook_pattern="bold claim",
        emoji_usage="minimal",
        hashtag_style="none",
        cta_style="implicit",
        vocabulary="technical",
        formatting="short lines",
    )
    assert style.tone == "direct"
    assert style.avg_length == "180 chars"


def test_style_profile_serialization():
    style = PlatformStyle(
        tone="t", avg_length="m", hook_pattern="h", emoji_usage="e",
        hashtag_style="h", cta_style="c", vocabulary="v", formatting="f",
    )
    profile = StyleProfile(twitter=style, linkedin=style)
    data = profile.model_dump()
    assert "twitter" in data
    assert "linkedin" in data
    assert data["twitter"]["tone"] == "t"


def test_draft_creation():
    draft = Draft(
        platform="twitter",
        content="Test tweet content",
        draft_type="single",
        source_file="test.md",
        generated_at=datetime.now(timezone.utc),
        image_suggestion="a nice image",
    )
    assert draft.platform == "twitter"
    assert draft.image_suggestion == "a nice image"


def test_suggestion_set():
    suggestion = PostSuggestion(
        topic="AI Agents",
        why_now="Trending topic",
        platforms=["twitter", "linkedin"],
        outline="Hook: bold claim\nBody: examples\nCTA: question",
        score=8.5,
    )
    ss = SuggestionSet(
        themes=["AI", "Docker"],
        suggestions=[suggestion],
        generated_at="2026-03-01T10:00:00Z",
    )
    assert len(ss.suggestions) == 1
    assert ss.suggestions[0].score == 8.5
    assert "AI" in ss.themes
