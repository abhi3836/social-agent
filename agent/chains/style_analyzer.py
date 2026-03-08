"""Style Analyzer — extract a StyleProfile from sample posts."""

import logging
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from config import AgentConfig
from models.style_profile import PlatformStyle, StyleProfile
from tools.file_reader import FileReader

logger = logging.getLogger("social-agent")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "style_analysis.txt"


class StyleAnalyzer:
    def __init__(self, config: AgentConfig, file_reader: FileReader):
        self.config = config
        self.file_reader = file_reader
        self.llm = ChatAnthropic(
            model=config.claude_model,
            api_key=config.anthropic_api_key,
            max_tokens=2000,
        )
        self.prompt_template = PromptTemplate.from_file(str(PROMPT_PATH))
        self.parser = JsonOutputParser()

    def analyze(self) -> StyleProfile:
        """Analyze style references and return a StyleProfile."""
        twitter_samples = self.file_reader.read_style_reference("twitter")
        linkedin_samples = self.file_reader.read_style_reference("linkedin")

        if not twitter_samples and not linkedin_samples:
            raise ValueError(
                "No style reference files found. "
                "Add samples to input/style-reference/twitter-samples.md "
                "and/or input/style-reference/linkedin-samples.md"
            )

        twitter_style = (
            self._analyze_platform("twitter", twitter_samples)
            if twitter_samples
            else self._default_style()
        )
        linkedin_style = (
            self._analyze_platform("linkedin", linkedin_samples)
            if linkedin_samples
            else self._default_style()
        )

        profile = StyleProfile(twitter=twitter_style, linkedin=linkedin_style)
        logger.info("Style analysis complete.")
        return profile

    def _analyze_platform(self, platform: str, samples: str) -> PlatformStyle:
        chain = self.prompt_template | self.llm | self.parser
        result = chain.invoke({"platform": platform, "samples": samples})
        return PlatformStyle(**result)

    def _default_style(self) -> PlatformStyle:
        return PlatformStyle(
            tone="professional, conversational",
            avg_length="medium",
            hook_pattern="direct statement",
            emoji_usage="minimal",
            hashtag_style="minimal",
            cta_style="question",
            vocabulary="accessible technical",
            formatting="short paragraphs",
        )
