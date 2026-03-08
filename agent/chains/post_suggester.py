"""Post Suggester — proactively generate post ideas based on style and themes."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from config import AgentConfig
from models.style_profile import StyleProfile
from models.suggestion import PostSuggestion, SuggestionSet
from tools.file_reader import FileReader
from tools.file_writer import FileWriter

logger = logging.getLogger("social-agent")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "suggestion.txt"


class PostSuggester:
    def __init__(
        self,
        config: AgentConfig,
        file_reader: FileReader,
        file_writer: FileWriter,
    ):
        self.config = config
        self.file_reader = file_reader
        self.file_writer = file_writer
        self.llm = ChatAnthropic(
            model=config.claude_model,
            api_key=config.anthropic_api_key,
            max_tokens=4000,
        )
        self.prompt = PromptTemplate.from_file(str(PROMPT_PATH))
        self.parser = JsonOutputParser()

    def suggest(self, style_profile: StyleProfile) -> SuggestionSet:
        """Generate post suggestions and write them to disk."""
        # Gather recent raw thoughts for theme extraction
        recent_files = self.file_reader.list_raw_thoughts()[-5:]
        recent_content = ""
        for fname in recent_files:
            content = self.file_reader.read_raw_thought(fname)
            recent_content += f"\n--- {fname} ---\n{content}\n"

        chain = self.prompt | self.llm | self.parser
        result = chain.invoke(
            {
                "style_profile": style_profile.model_dump_json(),
                "recent_themes": recent_content
                if recent_content
                else "No recent thoughts available.",
                "current_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "count": self.config.suggestion_count,
            }
        )

        suggestion_set = SuggestionSet(
            themes=result.get("themes", []),
            suggestions=[
                PostSuggestion(**s) for s in result.get("suggestions", [])
            ],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # Format and write to file
        formatted = self._format_suggestions(suggestion_set)
        self.file_writer.write_suggestions(formatted)

        logger.info(f"Generated {len(suggestion_set.suggestions)} suggestions.")
        return suggestion_set

    @staticmethod
    def _format_suggestions(suggestion_set: SuggestionSet) -> str:
        """Format suggestions as readable markdown."""
        lines = [
            f"# Post Suggestions — {suggestion_set.generated_at[:10]}",
            f"Generated based on your recent themes: {', '.join(suggestion_set.themes)}",
            "",
            "---",
            "",
        ]
        for i, s in enumerate(suggestion_set.suggestions, 1):
            lines.extend(
                [
                    f"## Suggestion {i} (Score: {s.score}/10)",
                    f"**Topic:** {s.topic}",
                    f"**Why now:** {s.why_now}",
                    f"**Platform:** {', '.join(s.platforms)}",
                    f"**Outline:**",
                    s.outline,
                    "",
                ]
            )
        return "\n".join(lines)
