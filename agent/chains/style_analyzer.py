"""Style Analyzer — load the author's voice profile from disk."""

import logging

from config import AgentConfig
from models.style_profile import VoiceProfile
from tools.file_reader import FileReader

logger = logging.getLogger("social-agent")


class StyleAnalyzer:
    def __init__(self, config: AgentConfig, file_reader: FileReader):
        self.config = config
        self.file_reader = file_reader

    def analyze(self) -> VoiceProfile:
        """Read the voice profile file and return a VoiceProfile."""
        voice = self.file_reader.read_voice_profile()
        if not voice:
            raise ValueError(
                "No voice profile found. "
                "Add a file to input/style-reference/ (e.g. voice-profile.md)."
            )
        logger.info("Voice profile loaded.")
        return VoiceProfile(voice=voice)
