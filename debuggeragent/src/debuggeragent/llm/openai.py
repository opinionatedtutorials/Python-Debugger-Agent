"""OpenAI LLM provider."""

from openai import AsyncOpenAI

from debuggeragent.llm.base import BaseLLMProvider, LLMResponse
from debuggeragent.utils.config import OpenAIConfig


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(self, config: OpenAIConfig | None = None):
        self.config = config or OpenAIConfig()
        self._client: AsyncOpenAI | None = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return "gpt-4o-mini"

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self.config.api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY or configure in config.")
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate completion using OpenAI."""
        model_name = self.get_model(model)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            return LLMResponse(
                content=content,
                model=model_name,
                usage=usage,
                raw=response.model_dump(),
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI error: {e}")

    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return bool(self.config.api_key)
