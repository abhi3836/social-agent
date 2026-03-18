"""Style profile schema — single voice profile for all platforms."""

from pydantic import BaseModel


class VoiceProfile(BaseModel):
    voice: str


# Alias kept so imports elsewhere resolve without change
StyleProfile = VoiceProfile
