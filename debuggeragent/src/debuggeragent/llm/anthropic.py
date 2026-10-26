"""Anthropic LLM provider."""

from anthropic import AsyncAnthropic

from debuggeragent.llm.base import BaseLLMProvider, LLMResponse
from debuggeragent.utils.config import AnthropicConfig


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API provider."""

    def __init__(self, config: AnthropicConfig | None = None):
        self.config = config or AnthropicConfig()
        self._client: AsyncAnthropic | None = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return "claude-3-5-haiku-20241022"

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            api_key = self.config.api_key
            if not api_key:
                raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY or configure in config.")
            self._client = AsyncAnthropic(api_key=api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate completion using Anthropic."""
        model_name = self.get_model(model)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.client.messages.create(
                model=model_name,
                messages=messages,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 4096,
            )

            content = response.content[0].text if response.content else ""
            usage = {
                "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                "completion_tokens": response.usage.output_tokens if response.usage else 0,
                "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
            }

            return LLMResponse(
                content=content,
                model=model_name,
                usage=usage,
                raw=response.model_dump(),
            )

        except Exception as e:
            raise RuntimeError(f"Anthropic error: {e}")

    def is_available(self) -> bool:
        """Check if Anthropic is configured."""
        return bool(self.config.api_key)
