"""Card Generator — converts raw thought into styled HTML stat cards."""

import base64
import logging
import re
from datetime import datetime
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from config import AgentConfig
from tools.file_writer import FileWriter

logger = logging.getLogger("social-agent")

_SYSTEM_PROMPT = (
    "You are an expert frontend developer specialising in dark, "
    "monospace-aesthetic stat cards. You produce complete, self-contained HTML files "
    "— no external dependencies except Google Fonts."
)

_HUMAN_TEMPLATE = """\
I'm going to give you a reference image that shows the exact \
visual style I want, followed by a list of card messages. Your job is to generate \
a single complete HTML page containing one card per message, faithfully matching \
the reference style.

=== CARD MESSAGES ===
{card_messages}

=== STYLE REQUIREMENTS (inferred from the reference image) ===
1. Background: near-black (#0a0a0a) card on a light grey (#f0f0f0) page background.
2. Typography: Space Mono (700) for large numbers, IBM Plex Mono (300/400/600) for \
   all other text. ALL text is uppercase with generous letter-spacing.
3. Layout: cards are square (~420 × 420 px), padding ~44 px, centred text.
4. Structure per card (top → bottom):
   - Large number or primary stat (font-size ~72 px, Space Mono Bold)
   - Two-line title (font-size ~22 px, uppercase, IBM Plex Mono)
   - Small subtitle line (font-size ~9 px, muted #888, uppercase)
   - 1 px horizontal divider (#333)
   - A relevant SVG icon (stroke: white, fill: none, ~52 × 52 px) — pick one \
     that semantically matches the card message
   - Short description (font-size ~10 px, muted #aaa, uppercase, line-height 1.8)
   - A simple bottom diagram relevant to the stat (bar chart, grid, flow arrows, \
     clock tick-marks, etc.)
5. All text and diagrams are centre-aligned.
6. Do NOT use any JS framework or external CSS library.
7. Respond with ONLY the complete HTML — no explanation, no markdown fences.

Analyse the reference image carefully and match its aesthetic precisely."""


class CardGenerator:
    def __init__(self, config: AgentConfig, file_writer: FileWriter):
        self.config = config
        self.file_writer = file_writer
        self.llm = ChatAnthropic(
            model="claude-opus-4-6",
            api_key=config.anthropic_api_key,
            max_tokens=8192,
        )

    def generate(self, inputs: list[str], reference_image: Path) -> Path:
        """Generate an HTML card page from `inputs` guided by `reference_image`.

        Args:
            inputs:          List of card message strings.
            reference_image: Path to the style-reference image.

        Returns:
            Path to the written HTML file.
        """
        if not inputs:
            raise ValueError("Provide at least one card message.")
        reference_image = self._resolve_reference(reference_image)

        img_b64, img_media_type = self._encode_image(reference_image)
        card_messages_str = "\n".join(f"  • {msg}" for msg in inputs)
        human_text = _HUMAN_TEMPLATE.format(card_messages=card_messages_str)

        message = HumanMessage(
            content=[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_media_type,
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": human_text},
            ]
        )

        logger.info(f"Generating {len(inputs)} card(s) via Claude (claude-opus-4-6)")
        prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM_PROMPT), message])
        result = (prompt | self.llm).invoke({})

        html = self._extract_html(result.content)
        return self._save(html)

    def _save(self, html: str) -> Path:
        output_dir = Path(self.config.workspace_root) / "output" / "cards"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"cards_{timestamp}.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info(f"Card HTML saved → {out_path}")
        return out_path

    @staticmethod
    def _resolve_reference(path: Path) -> Path:
        """Resolve a directory to its first image file, or validate a direct path."""
        _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        if path.is_dir():
            for ext in _IMAGE_EXTS:
                matches = sorted(path.glob(f"*{ext}"))
                if matches:
                    return matches[0]
            raise FileNotFoundError(
                f"No image file found in reference directory: {path}"
            )
        if not path.exists():
            raise FileNotFoundError(
                f"Reference image not found: {path}\n"
                "Place your reference image at that path or pass --reference <path>."
            )
        return path

    @staticmethod
    def _encode_image(path: Path) -> tuple[str, str]:
        media_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_type_map.get(path.suffix.lower(), "image/png")
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8"), media_type

    @staticmethod
    def html_to_png(html_path: Path) -> Path:
        """Screenshot an HTML file to a PNG using a headless Chromium browser.

        Args:
            html_path: Path to the HTML file to capture.

        Returns:
            Path to the written PNG file (same directory, same stem).
        """
        from playwright.sync_api import sync_playwright

        html_path = Path(html_path).resolve()
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        png_path = html_path.with_suffix(".png")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(html_path.as_uri())
            page.wait_for_load_state("networkidle")
            card_el = page.query_selector(".card")
            card_el.screenshot(path=str(png_path))
            browser.close()

        logger.info(f"Card PNG saved → {png_path}")
        return png_path

    @staticmethod
    def _extract_html(raw: str) -> str:
        match = re.search(r"```(?:html)?\s*(<!DOCTYPE.*?)</?\\s*```", raw, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        idx = raw.lower().find("<!doctype")
        if idx != -1:
            return raw[idx:].strip()
        return raw.strip()
