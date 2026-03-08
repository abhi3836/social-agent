"""Tests for FileReader and FileWriter."""

import json
from pathlib import Path

from tools.file_reader import FileReader
from tools.file_writer import FileWriter


def test_file_reader_list_raw_thoughts(tmp_path):
    raw_dir = tmp_path / "input" / "raw-thoughts"
    raw_dir.mkdir(parents=True)
    (raw_dir / "2026-03-01-topic.md").write_text("content 1")
    (raw_dir / "2026-03-02-topic.md").write_text("content 2")

    reader = FileReader(str(tmp_path))
    thoughts = reader.list_raw_thoughts()
    assert thoughts == ["2026-03-01-topic.md", "2026-03-02-topic.md"]


def test_file_reader_read_raw_thought(tmp_path):
    raw_dir = tmp_path / "input" / "raw-thoughts"
    raw_dir.mkdir(parents=True)
    (raw_dir / "test.md").write_text("Hello world")

    reader = FileReader(str(tmp_path))
    content = reader.read_raw_thought("test.md")
    assert content == "Hello world"


def test_file_reader_list_unprocessed(tmp_path):
    raw_dir = tmp_path / "input" / "raw-thoughts"
    raw_dir.mkdir(parents=True)
    (raw_dir / "2026-03-01-a.md").write_text("a")
    (raw_dir / "2026-03-02-b.md").write_text("b")

    output_dir = tmp_path / "output" / "drafts"
    output_dir.mkdir(parents=True)
    (output_dir / "2026-03-01-a").mkdir()  # already processed

    reader = FileReader(str(tmp_path))
    unprocessed = reader.list_unprocessed_thoughts(output_dir)
    assert unprocessed == ["2026-03-02-b.md"]


def test_file_reader_style_reference(tmp_path):
    style_dir = tmp_path / "input" / "style-reference"
    style_dir.mkdir(parents=True)
    (style_dir / "twitter-samples.md").write_text("sample tweets")

    reader = FileReader(str(tmp_path))
    assert reader.read_style_reference("twitter") == "sample tweets"
    assert reader.read_style_reference("linkedin") is None


def test_file_writer_write_draft(tmp_path):
    writer = FileWriter(str(tmp_path))
    path = writer.write_draft("2026-03-01-test.md", "twitter", "Draft content")
    assert path.exists()
    assert path.read_text() == "Draft content"
    assert path.name == "twitter-draft.md"
    assert path.parent.name == "2026-03-01-test"


def test_file_writer_write_metadata(tmp_path):
    writer = FileWriter(str(tmp_path))
    metadata = {"source": "test.md", "model": "claude"}
    path = writer.write_metadata("test.md", metadata)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["source"] == "test.md"


def test_file_writer_write_suggestions(tmp_path):
    writer = FileWriter(str(tmp_path))
    path = writer.write_suggestions("# Suggestions\nContent here")
    assert path.exists()
    assert "Suggestions" in path.read_text()


def test_file_writer_write_error(tmp_path):
    writer = FileWriter(str(tmp_path))
    path = writer.write_error("test.md", "Something went wrong")
    assert path.exists()
    assert path.read_text() == "Something went wrong"
    assert path.name == "error.log"
