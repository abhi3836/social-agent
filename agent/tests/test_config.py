"""Tests for AgentConfig loading."""


def test_config_loads_with_explicit_values():
    from config import AgentConfig

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        claude_model="claude-sonnet-4-20250514",
        post_platforms=["twitter", "linkedin"],
        log_level="DEBUG",
    )
    assert config.anthropic_api_key == "sk-ant-test"
    assert config.claude_model == "claude-sonnet-4-20250514"
    assert config.post_platforms == ["twitter", "linkedin"]
    assert config.log_level == "DEBUG"


def test_config_defaults():
    from config import AgentConfig

    config = AgentConfig(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
    )
    assert config.claude_model == "claude-sonnet-4-20250514"
    assert config.suggestion_count == 5
    assert config.style_reanalyze is False
    assert config.workspace_root == "/home/agent/workspace"
    assert config.openai_api_key is None
    assert config.sd_api_url is None
