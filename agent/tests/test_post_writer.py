"""Tests for PostWriter chain."""

from unittest.mock import patch

from models.style_profile import PlatformStyle, StyleProfile


def _make_style_profile():
    style = PlatformStyle(
        tone="direct", avg_length="180 chars", hook_pattern="bold claim",
        emoji_usage="minimal", hashtag_style="none", cta_style="implicit",
        vocabulary="technical", formatting="short lines",
    )
    return StyleProfile(twitter=style, linkedin=style)


SAMPLE_DRAFT = "# Draft\nContent here\n**Image suggestion:** A nice image"


@patch("chains.post_writer.ChatAnthropic")
def test_write_produces_drafts_for_both_platforms(mock_llm_cls):
    from config import AgentConfig
    from chains.post_writer import PostWriter

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        post_platforms=["twitter", "linkedin"],
    )
    writer = PostWriter(config)

    with patch.object(writer, "_write_twitter", return_value=SAMPLE_DRAFT):
        with patch.object(writer, "_write_linkedin", return_value=SAMPLE_DRAFT):
            with patch.object(writer, "_self_critique", side_effect=lambda p, d, s: d):
                drafts = writer.write("Raw thought", _make_style_profile(), "test.md")

    assert len(drafts) == 2
    assert drafts[0].platform == "twitter"
    assert drafts[1].platform == "linkedin"
    assert drafts[0].image_suggestion == "A nice image"


@patch("chains.post_writer.ChatAnthropic")
def test_write_respects_platform_config(mock_llm_cls):
    from config import AgentConfig
    from chains.post_writer import PostWriter

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        post_platforms=["twitter"],
    )
    writer = PostWriter(config)

    with patch.object(writer, "_write_twitter", return_value=SAMPLE_DRAFT):
        with patch.object(writer, "_self_critique", side_effect=lambda p, d, s: d):
            drafts = writer.write("Raw thought", _make_style_profile(), "test.md")

    assert len(drafts) == 1
    assert drafts[0].platform == "twitter"


def test_extract_image_suggestion():
    from chains.post_writer import PostWriter

    content = "Some draft\n**Image suggestion:** A lock inside a container"
    assert PostWriter._extract_image_suggestion(content) == "A lock inside a container"
    assert PostWriter._extract_image_suggestion("No suggestion here") is None
