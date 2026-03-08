"""Agent configuration via Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class AgentConfig(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: Optional[str] = None
    sd_api_url: Optional[str] = None
    post_platforms: list[str] = Field(default=["twitter", "linkedin"])
    suggestion_count: int = 5
    style_reanalyze: bool = False
    log_level: str = "INFO"
    workspace_root: str = "/home/agent/workspace"

    model_config = {
        "env_file": "/home/agent/.config/.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
