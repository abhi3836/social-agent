"""Post Writer — transform raw thoughts into platform-specific drafts."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate

from config import AgentConfig
from models.draft import Draft
from models.style_profile import StyleProfile
from tools.twitter_publisher import TwitterPublisher

logger = logging.getLogger("social-agent")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class PostWriter:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = ChatAnthropic(
            model=config.claude_model,
            api_key=config.anthropic_api_key,
            max_tokens=4000,
        )
        self.twitter_prompt = PromptTemplate.from_file(
            str(PROMPTS_DIR / "twitter_writer.txt"),
        )
        self.linkedin_prompt = PromptTemplate.from_file(
            str(PROMPTS_DIR / "linkedin_writer.txt"),
        )
        self.critique_prompt = PromptTemplate.from_file(
            str(PROMPTS_DIR / "self_critique.txt"),
        )

    def write(
        self,
        raw_thought: str,
        style_profile: StyleProfile,
        source_filename: str,
        skip_auto_post: bool = False,
    ) -> list[Draft]:
        """Generate drafts for all configured platforms."""
        drafts = []

        if "twitter" in self.config.post_platforms:
            twitter_content = self._write_twitter(raw_thought, style_profile)
            twitter_content = self._self_critique(
                "twitter", twitter_content, style_profile
            )
            image_suggestion = self._extract_image_suggestion(twitter_content)
            tweet_ids = [] if skip_auto_post else self._auto_post_twitter(twitter_content)
            drafts.append(
                Draft(
                    platform="twitter",
                    content=twitter_content,
                    draft_type="thread" if "Tweet 2" in twitter_content else "single",
                    source_file=source_filename,
                    generated_at=datetime.now(timezone.utc),
                    image_suggestion=image_suggestion,
                    posted_ids=tweet_ids,
                )
            )

        if "linkedin" in self.config.post_platforms:
            linkedin_content = self._write_linkedin(raw_thought, style_profile)
            linkedin_content = self._self_critique(
                "linkedin", linkedin_content, style_profile
            )
            image_suggestion = self._extract_image_suggestion(linkedin_content)
            drafts.append(
                Draft(
                    platform="linkedin",
                    content=linkedin_content,
                    draft_type="single",
                    source_file=source_filename,
                    generated_at=datetime.now(timezone.utc),
                    image_suggestion=image_suggestion,
                )
            )

        return drafts

    def _write_twitter(self, raw_thought: str, style: StyleProfile) -> str:
        chain = self.twitter_prompt | self.llm
        result = chain.invoke(
            {
                "voice_profile": style.voice,
                "raw_thought": raw_thought,
            }
        )
        return result.content

    def _write_linkedin(self, raw_thought: str, style: StyleProfile) -> str:
        chain = self.linkedin_prompt | self.llm
        result = chain.invoke(
            {
                "voice_profile": style.voice,
                "raw_thought": raw_thought,
            }
        )
        return result.content

    def _self_critique(
        self, platform: str, draft: str, style: StyleProfile
    ) -> str:
        chain = self.critique_prompt | self.llm
        result = chain.invoke(
            {
                "platform": platform,
                "voice_profile": style.voice,
                "draft": draft,
            }
        )
        return result.content

    def _auto_post_twitter(self, content: str) -> list[str]:
        """Post to Twitter if auto-post is enabled and credentials are configured."""
        if not self.config.twitter_auto_post:
            return []
        try:
            publisher = TwitterPublisher(self.config)
            return publisher.post(content)
        except Exception as e:
            logger.error(f"Twitter auto-post failed: {e}")
            return []

    @staticmethod
    def _extract_image_suggestion(content: str) -> str | None:
        """Extract the image suggestion line from draft content."""
        match = re.search(r"\*\*Image suggestion:\*\*\s*(.+)", content)
        return match.group(1).strip() if match else None
