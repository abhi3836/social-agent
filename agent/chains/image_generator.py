"""Image Generator — create post-accompanying images from drafts."""

import io
import logging
from pathlib import Path
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from PIL import Image

from config import AgentConfig
from tools.file_writer import FileWriter
from tools.image_api import ImageAPIClient
from utils.validators import PLATFORM_SPECS

logger = logging.getLogger("social-agent")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "image_brief.txt"


class ImageGenerator:
    def __init__(self, config: AgentConfig, file_writer: FileWriter):
        self.config = config
        self.file_writer = file_writer
        self.llm = ChatAnthropic(
            model=config.claude_model,
            api_key=config.anthropic_api_key,
            max_tokens=1000,
        )
        self.image_client = ImageAPIClient(
            openai_api_key=config.openai_api_key,
            sd_api_url=config.sd_api_url,
        )
        self.brief_prompt = PromptTemplate.from_file(str(PROMPT_PATH))

    async def generate(
        self,
        draft_content: str,
        image_suggestion: Optional[str],
        platform: str,
        source_filename: str,
    ) -> Optional[Path]:
        """Generate an image for a draft. Returns path or None on failure."""
        try:
            spec = PLATFORM_SPECS[platform]

            # Step 1: Generate visual brief via Claude
            chain = self.brief_prompt | self.llm
            brief_result = chain.invoke(
                {
                    "platform": platform,
                    "width": spec["width"],
                    "height": spec["height"],
                    "draft_content": draft_content,
                    "image_suggestion": image_suggestion
                    or "a relevant professional image",
                }
            )
            image_prompt = brief_result.content
            logger.info(f"Generated image brief for {platform}")

            # Step 2: Call image API
            raw_bytes = await self.image_client.generate(
                prompt=image_prompt,
                size=f"{spec['width']}x{spec['height']}",
            )

            # Step 3: Validate and resize if needed
            final_bytes = self._validate_and_resize(raw_bytes, platform)

            # Step 4: Save to disk
            return self.file_writer.write_image(
                source_filename, platform, final_bytes
            )

        except Exception as e:
            logger.error(f"Image generation failed for {platform}: {e}")
            self.file_writer.write_error(
                source_filename,
                f"Image generation failed for {platform}: {e}",
            )
            return None

    @staticmethod
    def _validate_and_resize(image_bytes: bytes, platform: str) -> bytes:
        """Resize image to exact platform specs if dimensions don't match."""
        spec = PLATFORM_SPECS[platform]
        img = Image.open(io.BytesIO(image_bytes))

        if img.size != (spec["width"], spec["height"]):
            img = img.resize((spec["width"], spec["height"]), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
