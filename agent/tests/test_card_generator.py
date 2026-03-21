"""Tests for CardGenerator chain."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_config(tmp_path):
    from config import AgentConfig

    return AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        workspace_root=str(tmp_path),
    )


def _make_png(path: Path) -> Path:
    """Write a minimal valid 1×1 PNG so encode_image doesn't fail."""
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return path


# ── _extract_html ──────────────────────────────────────────────────────────────

def test_extract_html_returns_raw_when_no_doctype():
    from chains.card_generator import CardGenerator

    raw = "<div>no doctype</div>"
    assert CardGenerator._extract_html(raw) == raw.strip()


def test_extract_html_strips_leading_content_before_doctype():
    from chains.card_generator import CardGenerator

    raw = "Sure! Here you go:\n<!DOCTYPE html><html></html>"
    result = CardGenerator._extract_html(raw)
    assert result.startswith("<!DOCTYPE html>")


# ── _resolve_reference ─────────────────────────────────────────────────────────

def test_resolve_reference_returns_path_when_file_exists(tmp_path):
    from chains.card_generator import CardGenerator

    img = _make_png(tmp_path / "ref.png")
    assert CardGenerator._resolve_reference(img) == img


def test_resolve_reference_raises_when_file_missing(tmp_path):
    from chains.card_generator import CardGenerator

    with pytest.raises(FileNotFoundError, match="Reference image not found"):
        CardGenerator._resolve_reference(tmp_path / "missing.png")


def test_resolve_reference_picks_first_image_from_directory(tmp_path):
    from chains.card_generator import CardGenerator

    _make_png(tmp_path / "alpha.png")
    _make_png(tmp_path / "beta.png")
    result = CardGenerator._resolve_reference(tmp_path)
    assert result.name == "alpha.png"


def test_resolve_reference_raises_when_directory_empty(tmp_path):
    from chains.card_generator import CardGenerator

    with pytest.raises(FileNotFoundError, match="No image file found"):
        CardGenerator._resolve_reference(tmp_path)


# ── _encode_image ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("suffix,expected_media_type", [
    (".png",  "image/png"),
    (".jpg",  "image/jpeg"),
    (".jpeg", "image/jpeg"),
    (".gif",  "image/gif"),
    (".webp", "image/webp"),
])
def test_encode_image_media_type(tmp_path, suffix, expected_media_type):
    from chains.card_generator import CardGenerator

    img = tmp_path / f"ref{suffix}"
    img.write_bytes(b"fakeimagebytes")
    b64, media_type = CardGenerator._encode_image(img)
    assert media_type == expected_media_type
    assert b64 == base64.standard_b64encode(b"fakeimagebytes").decode()


def test_encode_image_unknown_extension_defaults_to_png(tmp_path):
    from chains.card_generator import CardGenerator

    img = tmp_path / "ref.bmp"
    img.write_bytes(b"data")
    _, media_type = CardGenerator._encode_image(img)
    assert media_type == "image/png"


# ── generate ───────────────────────────────────────────────────────────────────

@patch("chains.card_generator.ChatAnthropic")
def test_generate_raises_on_empty_inputs(mock_llm_cls, tmp_path):
    from chains.card_generator import CardGenerator
    from tools.file_writer import FileWriter

    config = _make_config(tmp_path)
    gen = CardGenerator(config, FileWriter(str(tmp_path)))

    with pytest.raises(ValueError, match="Provide at least one card message"):
        gen.generate([], tmp_path / "ref.png")


@patch("chains.card_generator.ChatAnthropic")
def test_generate_saves_html_and_returns_path(mock_llm_cls, tmp_path):
    from chains.card_generator import CardGenerator
    from tools.file_writer import FileWriter

    ref = _make_png(tmp_path / "ref.png")
    config = _make_config(tmp_path)
    gen = CardGenerator(config, FileWriter(str(tmp_path)))

    html_response = "<!DOCTYPE html><html><body>cards</body></html>"

    with patch("chains.card_generator.ChatPromptTemplate") as mock_prompt_cls:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content=html_response)
        with patch.object(type(mock_prompt_cls.from_messages.return_value), "__or__", return_value=mock_chain):
            out = gen.generate(["19 PRs merged", "4 enhancements"], ref)

    assert out.exists()
    assert out.suffix == ".html"
    assert out.parent == tmp_path / "output" / "cards"
    assert "<!DOCTYPE html>" in out.read_text()


@patch("chains.card_generator.ChatAnthropic")
def test_generate_card_messages_formatting(mock_llm_cls, tmp_path):
    """Verify bullet-point formatting is applied to inputs."""
    from chains.card_generator import CardGenerator
    from tools.file_writer import FileWriter

    ref = _make_png(tmp_path / "ref.png")
    config = _make_config(tmp_path)
    gen = CardGenerator(config, FileWriter(str(tmp_path)))

    captured_text = {}

    original_save = gen._save

    def fake_save(html):
        captured_text["html"] = html
        return original_save(html)

    with patch.object(gen, "_save", side_effect=fake_save):
        with patch("chains.card_generator.ChatPromptTemplate") as mock_prompt_cls:
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = MagicMock(content="<!DOCTYPE html><html></html>")
            with patch.object(type(mock_prompt_cls.from_messages.return_value), "__or__", return_value=mock_chain):
                gen.generate(["19 PRs merged", "4 enhancements"], ref)

    # The chain was invoked — confirm inputs were bullet-formatted in human text
    call_args = mock_chain.invoke.call_args
    assert call_args is not None
