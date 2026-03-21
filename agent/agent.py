#!/usr/bin/env python3
"""Social Media Agent — CLI Entry Point.

Transform raw thoughts into polished social media posts.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from chains.card_generator import CardGenerator
from chains.image_generator import ImageGenerator

from chains.post_writer import PostWriter
from chains.post_suggester import PostSuggester
from chains.style_analyzer import StyleAnalyzer
from config import AgentConfig
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from utils.logger import setup_logger
from utils.validators import validate_raw_thought

# Initialize shared components
config = AgentConfig()
logger = setup_logger(config.log_level)

file_reader = FileReader(config.workspace_root)
file_writer = FileWriter(config.workspace_root)


def _get_style_profile():
    """Analyze style references (cached per invocation)."""
    analyzer = StyleAnalyzer(config, file_reader)
    return analyzer.analyze()


def _process_thought(filename, style_profile, writer, img_gen=None, card_gen=None):
    """Process a single raw thought through the full pipeline."""
    logger.info(f"Processing: {filename}")

    raw_thought = file_reader.read_raw_thought(filename)

    valid, err = validate_raw_thought(raw_thought)
    if not valid:
        file_writer.write_error(filename, err)
        logger.warning(f"Skipping {filename}: {err}")
        return

    # Generate drafts (skip auto-post when card_gen handles posting with image)
    drafts = writer.write(raw_thought, style_profile, filename, skip_auto_post=card_gen is not None)
    for draft in drafts:
        file_writer.write_draft(filename, draft.platform, draft.content)

    # Generate images — card-based (Twitter only) or API-based
    if card_gen is not None:
        twitter_draft = next((d for d in drafts if d.platform == "twitter"), None)
        if twitter_draft:
            reference_image = (
                Path(config.workspace_root) / "input" / "image-reference" / "reference.png"
            )
            inputs = [line.strip() for line in raw_thought.splitlines() if line.strip()]
            try:
                html_path = card_gen.generate(inputs, reference_image)
                png_path = card_gen.html_to_png(html_path)
                file_writer.write_image(filename, "twitter", png_path.read_bytes())
                logger.info(f"Card image saved for twitter: {png_path}")
                if config.twitter_auto_post:
                    from tools.twitter_publisher import TwitterPublisher
                    publisher = TwitterPublisher(config)
                    posted_ids = publisher.post(twitter_draft.content, image_path=png_path)
                    twitter_draft.posted_ids = posted_ids
            except Exception as e:
                logger.error(f"Card generation failed for {filename}: {e}")
                file_writer.write_error(filename, f"Card generation failed: {e}")
    elif config.openai_api_key or config.sd_api_url:
        for draft in drafts:
            asyncio.run(
                img_gen.generate(
                    draft_content=draft.content,
                    image_suggestion=draft.image_suggestion,
                    platform=draft.platform,
                    source_filename=filename,
                )
            )
    else:
        logger.info("No image API configured — skipping image generation.")

    # Write metadata
    metadata = {
        "source_file": f"raw-thoughts/{filename}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claude_model": config.claude_model,
        "image_model": "dall-e-3"
        if config.openai_api_key
        else ("stable-diffusion" if config.sd_api_url else "none"),
        "platforms": [d.platform for d in drafts],
    }
    file_writer.write_metadata(filename, metadata)
    file_writer.archive_raw_thought(filename)
    logger.info(f"Completed: {filename}")


@click.group()
def cli():
    """Social Media Agent — Transform raw thoughts into polished posts."""
    pass


@cli.command()
@click.option(
    "--input",
    "input_file",
    required=False,
    help="Specific raw thought filename to process.",
)
@click.option(
    "--all",
    "process_all",
    is_flag=True,
    help="Process all unprocessed thoughts.",
)
def write(input_file, process_all):
    """Generate platform-specific post drafts from raw thoughts."""
    style_profile = _get_style_profile()
    writer = PostWriter(config)
    img_gen = ImageGenerator(config, file_writer)

    if input_file:
        _process_thought(input_file, style_profile, writer, img_gen)
    elif process_all:
        output_dir = Path(config.workspace_root) / "output" / "drafts"
        unprocessed = file_reader.list_unprocessed_thoughts(output_dir)
        if not unprocessed:
            logger.info("No unprocessed thoughts found.")
            return
        for fname in unprocessed:
            try:
                _process_thought(fname, style_profile, writer, img_gen)
            except Exception as e:
                logger.error(f"Failed to process {fname}: {e}")
                file_writer.write_error(fname, str(e))
    else:
        click.echo("Specify --input <file> or --all")


@cli.command()
@click.option("--input", "input_file", required=False, help="Specific raw thought filename to generate cards from.")
@click.option("--messages", "-m", multiple=True, help="Explicit card messages (alternative to --input).")
@click.option(
    "--reference", "-r",
    default=None,
    help="Path to reference image or directory (default: <workspace>/input/image-reference/).",
)
def cards(input_file, messages, reference):
    """Generate styled HTML stat cards from a raw thought or explicit messages."""
    reference_image = Path(reference) if reference else Path(config.workspace_root) / "input" / "image-reference" / "reference.png"
    card_gen = CardGenerator(config, file_writer)

    if messages:
        inputs = list(messages)
    elif input_file:
        inputs = [line.strip() for line in file_reader.read_raw_thought(input_file).splitlines() if line.strip()]
    else:
        click.echo("Specify --input <file> or one or more --messages/-m values.")
        return

    out = card_gen.generate(inputs, reference_image)
    img = card_gen.html_to_png(out)
    click.echo(f"Cards saved → {img}")


@cli.command()
def suggest():
    """Generate proactive post suggestions."""
    style_profile = _get_style_profile()
    suggester = PostSuggester(config, file_reader, file_writer)
    result = suggester.suggest(style_profile)
    click.echo(f"Generated {len(result.suggestions)} suggestions.")


@cli.command()
@click.option("--draft", required=True, help="Path to draft folder.")
def image(draft):
    """Generate images for an existing draft."""
    img_gen = ImageGenerator(config, file_writer)
    draft_path = Path(draft)
    source_filename = draft_path.name + ".md"

    for platform in config.post_platforms:
        draft_file = draft_path / f"{platform}-draft.md"
        if draft_file.exists():
            content = draft_file.read_text(encoding="utf-8")
            asyncio.run(
                img_gen.generate(
                    draft_content=content,
                    image_suggestion="",
                    platform=platform,
                    source_filename=source_filename,
                )
            )


@cli.command()
@click.option("--all", "run_all", is_flag=True, default=True)
def run(run_all):
    """Full pipeline: write + image + suggest."""
    style_profile = _get_style_profile()
    writer = PostWriter(config)
    img_gen = ImageGenerator(config, file_writer)
    output_dir = Path(config.workspace_root) / "output" / "drafts"

    # Process all unprocessed thoughts
    unprocessed = file_reader.list_unprocessed_thoughts(output_dir)
    for fname in unprocessed:
        try:
            _process_thought(fname, style_profile, writer, img_gen)
        except Exception as e:
            logger.error(f"Failed: {fname}: {e}")
            file_writer.write_error(fname, str(e))

    # Generate suggestions
    suggester = PostSuggester(config, file_reader, file_writer)
    suggester.suggest(style_profile)


@cli.command()
@click.option("--interval", default=90, help="Polling interval in seconds (default: 90 = 15 sec).")
def watch(interval):
    """Watch mode — poll for new raw thoughts and auto-process."""
    logger.info(f"Watch mode started. Polling every {interval}s ({interval // 60}m).")
    style_profile = _get_style_profile()
    writer = PostWriter(config)
    card_gen = CardGenerator(config, file_writer)
    output_dir = Path(config.workspace_root) / "output" / "drafts"

    while True:
        unprocessed = file_reader.list_unprocessed_thoughts(output_dir)
        for fname in unprocessed:
            try:
                _process_thought(fname, style_profile, writer, card_gen=card_gen)
            except Exception as e:
                logger.error(f"Failed: {fname}: {e}")
                file_writer.write_error(fname, str(e))
        time.sleep(interval)


if __name__ == "__main__":
    cli()
