"""Configuration management for debuggeragent."""

import os
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import BaseModel, Field


class RunnerConfig(BaseModel):
    """Configuration for code execution."""
    timeout: int = Field(default=30, description="Execution timeout in seconds")
    command: str = Field(default="python", description="Command to run Python files")


class OllamaConfig(BaseModel):
    """Ollama-specific configuration."""
    host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    model: str = Field(default="llama3.1", description="Model name to use")


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""
    api_key: str | None = Field(default=None, description="OpenAI API key")


class AnthropicConfig(BaseModel):
    """Anthropic-specific configuration."""
    api_key: str | None = Field(default=None, description="Anthropic API key")


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    provider: str = Field(default="ollama", description="Provider: ollama, openai, anthropic")
    model: str = Field(default="llama3.1", description="Model name")
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)


class DocsConfig(BaseModel):
    """Documentation access configuration."""
    sources: list[str] = Field(default_factory=lambda: ["pydoc", "source", "stubs"])
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")


class FixerConfig(BaseModel):
    """Auto-fixer configuration."""
    interactive: bool = Field(default=True, description="Ask before applying fixes")
    max_iterations: int = Field(default=5, description="Maximum fix iterations")


class Config(BaseModel):
    """Main configuration."""
    runner: RunnerConfig = Field(default_factory=RunnerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    docs: DocsConfig = Field(default_factory=DocsConfig)
    fixer: FixerConfig = Field(default_factory=FixerConfig)


DEFAULT_CONFIG = Config()


def find_config_file() -> Path | None:
    """Find configuration file in standard locations."""
    # Project-local config
    local = Path.cwd() / ".debuggeragent.toml"
    if local.exists():
        return local

    # User config directory
    config_dir = Path.home() / ".config" / "debuggeragent"
    user = config_dir / "config.toml"
    if user.exists():
        return user

    return None


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file, merging with defaults."""
    config = DEFAULT_CONFIG.model_copy(deep=True)

    if config_path is None:
        config_path = find_config_file()

    if config_path and config_path.exists():
        with open(config_path, "rb") as f:
            file_config = tomli.load(f)

        # Merge with environment variable interpolation
        file_config = _interpolate_env_vars(file_config)
        config = _merge_config(config, file_config)

    # Also check environment variables for API keys
    config = _apply_env_overrides(config)

    return config


def _interpolate_env_vars(obj: Any) -> Any:
    """Recursively interpolate ${VAR} or $VAR in string values."""
    if isinstance(obj, str):
        # Handle ${VAR} and $VAR patterns
        import re
        def replace(match):
            var = match.group(1) or match.group(2)
            return os.environ.get(var, match.group(0))
        return re.sub(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)', replace, obj)
    elif isinstance(obj, dict):
        return {k: _interpolate_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_interpolate_env_vars(v) for v in obj]
    return obj


def _merge_config(base: Config, override: dict) -> Config:
    """Merge override dict into base config."""
    base_dict = base.model_dump()
    _deep_merge(base_dict, override)
    return Config.model_validate(base_dict)


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides."""
    # LLM provider overrides
    if provider := os.environ.get("DEBUGGERAGENT_PROVIDER"):
        config.llm.provider = provider
    if model := os.environ.get("DEBUGGERAGENT_MODEL"):
        config.llm.model = model
    if host := os.environ.get("DEBUGGERAGENT_OLLAMA_HOST"):
        config.llm.ollama.host = host

    # API keys
    if key := os.environ.get("OPENAI_API_KEY"):
        config.llm.openai.api_key = key
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        config.llm.anthropic.api_key = key

    return config


def save_config(config: Config, path: Path) -> None:
    """Save configuration to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(config.model_dump(exclude_none=True), f)
