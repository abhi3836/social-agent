"""Tests for PostSuggester chain."""

from unittest.mock import patch

from models.style_profile import PlatformStyle, StyleProfile
from models.suggestion import PostSuggestion, SuggestionSet


def _make_style_profile():
    style = PlatformStyle(
        tone="direct", avg_length="180 chars", hook_pattern="bold claim",
        emoji_usage="minimal", hashtag_style="none", cta_style="implicit",
        vocabulary="technical", formatting="short lines",
    )
    return StyleProfile(twitter=style, linkedin=style)


@patch("chains.post_suggester.ChatAnthropic")
def test_suggest_generates_and_writes(mock_llm_cls, tmp_path):
    raw_dir = tmp_path / "input" / "raw-thoughts"
    raw_dir.mkdir(parents=True)
    (raw_dir / "2026-03-01-test.md").write_text("Test thought about AI agents")

    from config import AgentConfig
    from tools.file_reader import FileReader
    from tools.file_writer import FileWriter
    from chains.post_suggester import PostSuggester

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        workspace_root=str(tmp_path),
        suggestion_count=2,
    )
    reader = FileReader(str(tmp_path))
    writer = FileWriter(str(tmp_path))
    suggester = PostSuggester(config, reader, writer)

    mock_llm_result = {
        "themes": ["AI agents", "security"],
        "suggestions": [
            {
                "topic": "Agent permissions",
                "why_now": "Trending topic",
                "platforms": ["twitter"],
                "outline": "Hook: bold claim\nBody: examples",
                "score": 8.0,
            }
        ],
    }

    with patch.object(suggester, "suggest") as mock_suggest:
        mock_suggest.return_value = SuggestionSet(
            themes=["AI agents", "security"],
            suggestions=[PostSuggestion(**mock_llm_result["suggestions"][0])],
            generated_at="2026-03-01T10:00:00Z",
        )
        result = suggester.suggest(_make_style_profile())

    assert isinstance(result, SuggestionSet)
    assert "AI agents" in result.themes
    assert len(result.suggestions) == 1


def test_format_suggestions():
    from chains.post_suggester import PostSuggester

    ss = SuggestionSet(
        themes=["AI", "Docker"],
        suggestions=[
            PostSuggestion(
                topic="Agent security",
                why_now="Hot topic",
                platforms=["twitter", "linkedin"],
                outline="Hook: bold\nBody: facts\nCTA: question",
                score=9.0,
            )
        ],
        generated_at="2026-03-01T10:00:00Z",
    )

    formatted = PostSuggester._format_suggestions(ss)
    assert "# Post Suggestions" in formatted
    assert "Agent security" in formatted
    assert "Score: 9.0/10" in formatted
    assert "AI, Docker" in formatted
