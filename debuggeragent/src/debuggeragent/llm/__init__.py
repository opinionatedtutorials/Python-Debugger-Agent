"""LLM provider package."""

from debuggeragent.llm.base import BaseLLMProvider, LLMResponse
from debuggeragent.llm.factory import create_provider, get_available_providers
from debuggeragent.llm.ollama import OllamaProvider

# Optional providers - only import if available
try:
    from debuggeragent.llm.openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None

try:
    from debuggeragent.llm.anthropic import AnthropicProvider
except ImportError:
    AnthropicProvider = None

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "OllamaProvider",
    "create_provider",
    "get_available_providers",
]

if OpenAIProvider is not None:
    __all__.append("OpenAIProvider")

if AnthropicProvider is not None:
    __all__.append("AnthropicProvider")
