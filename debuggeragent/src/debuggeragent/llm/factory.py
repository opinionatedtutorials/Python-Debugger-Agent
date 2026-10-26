"""LLM provider factory."""


from debuggeragent.llm.base import BaseLLMProvider
from debuggeragent.llm.ollama import OllamaProvider
from debuggeragent.utils.config import Config

# Optional providers
try:
    from debuggeragent.llm.openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from debuggeragent.llm.anthropic import AnthropicProvider
except ImportError:
    AnthropicProvider = None


def create_provider(config: Config, provider: str | None = None, model: str | None = None) -> BaseLLMProvider:
    """Create an LLM provider from configuration."""
    provider_name = provider or config.llm.provider
    llm_config = config.llm

    if provider_name == "ollama":
        ollama_config = llm_config.ollama
        if model:
            ollama_config = ollama_config.model_copy(update={"model": model})
        return OllamaProvider(ollama_config)

    elif provider_name == "openai":
        if OpenAIProvider is None:
            raise ValueError("OpenAI provider not available. Install with: pip install openai")
        openai_config = llm_config.openai
        return OpenAIProvider(openai_config)

    elif provider_name == "anthropic":
        if AnthropicProvider is None:
            raise ValueError("Anthropic provider not available. Install with: pip install anthropic")
        anthropic_config = llm_config.anthropic
        return AnthropicProvider(anthropic_config)

    else:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: ollama, openai, anthropic")


def get_available_providers(config: Config) -> list[str]:
    """Get list of available/configured providers."""
    available = []

    # Ollama is available if server is running
    ollama = OllamaProvider(config.llm.ollama)
    if ollama.is_available():
        available.append("ollama")

    # OpenAI available if API key set and package installed
    if config.llm.openai.api_key and OpenAIProvider is not None:
        available.append("openai")

    # Anthropic available if API key set and package installed
    if config.llm.anthropic.api_key and AnthropicProvider is not None:
        available.append("anthropic")

    return available
