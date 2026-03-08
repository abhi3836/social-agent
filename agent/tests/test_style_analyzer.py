"""Tests for StyleAnalyzer chain."""

from unittest.mock import patch

import pytest

from models.style_profile import PlatformStyle, StyleProfile


def _mock_style():
    return PlatformStyle(
        tone="direct, opinionated",
        avg_length="180 chars",
        hook_pattern="bold claim",
        emoji_usage="minimal",
        hashtag_style="none",
        cta_style="implicit",
        vocabulary="technical",
        formatting="short lines",
    )


@patch("chains.style_analyzer.ChatAnthropic")
def test_analyze_returns_style_profile(mock_llm_cls, tmp_path):
    style_dir = tmp_path / "input" / "style-reference"
    style_dir.mkdir(parents=True)
    (style_dir / "twitter-samples.md").write_text("Sample tweet content")
    (style_dir / "linkedin-samples.md").write_text("Sample LinkedIn content")

    from config import AgentConfig
    from tools.file_reader import FileReader
    from chains.style_analyzer import StyleAnalyzer

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        workspace_root=str(tmp_path),
    )
    reader = FileReader(str(tmp_path))
    analyzer = StyleAnalyzer(config, reader)

    with patch.object(analyzer, "_analyze_platform", return_value=_mock_style()):
        profile = analyzer.analyze()

    assert isinstance(profile, StyleProfile)
    assert profile.twitter.tone == "direct, opinionated"
    assert profile.linkedin.tone == "direct, opinionated"


@patch("chains.style_analyzer.ChatAnthropic")
def test_analyze_raises_on_missing_references(mock_llm_cls, tmp_path):
    (tmp_path / "input" / "style-reference").mkdir(parents=True)

    from config import AgentConfig
    from tools.file_reader import FileReader
    from chains.style_analyzer import StyleAnalyzer

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        workspace_root=str(tmp_path),
    )
    reader = FileReader(str(tmp_path))
    analyzer = StyleAnalyzer(config, reader)

    with pytest.raises(ValueError, match="No style reference files found"):
        analyzer.analyze()


@patch("chains.style_analyzer.ChatAnthropic")
def test_analyze_uses_default_for_missing_platform(mock_llm_cls, tmp_path):
    style_dir = tmp_path / "input" / "style-reference"
    style_dir.mkdir(parents=True)
    (style_dir / "twitter-samples.md").write_text("Sample tweets")

    from config import AgentConfig
    from tools.file_reader import FileReader
    from chains.style_analyzer import StyleAnalyzer

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        workspace_root=str(tmp_path),
    )
    reader = FileReader(str(tmp_path))
    analyzer = StyleAnalyzer(config, reader)

    with patch.object(analyzer, "_analyze_platform", return_value=_mock_style()):
        profile = analyzer.analyze()

    assert profile.twitter.tone == "direct, opinionated"
    assert profile.linkedin.tone == "professional, conversational"  # default
