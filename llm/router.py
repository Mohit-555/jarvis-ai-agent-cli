from typing import AsyncGenerator

from core.exceptions import ProviderNotFound
from llm.providers.base import BaseLLMProvider


class LLMRouter:
    def __init__(self, config: dict):
        self.config = config
        self._providers: dict[str, BaseLLMProvider] = {}

    def _get_provider_class(self, name: str):
        if name == 'ollama':
            from llm.providers.ollama import OllamaProvider
            return OllamaProvider
        elif name == 'openai':
            from llm.providers.openai import OpenAIProvider
            return OpenAIProvider
        elif name == 'anthropic':
            from llm.providers.anthropic import AnthropicProvider
            return AnthropicProvider
        elif name == 'gemini':
            from llm.providers.gemini import GeminiProvider
            return GeminiProvider
        elif name == 'openrouter':
            from llm.providers.openrouter import OpenRouterProvider
            return OpenRouterProvider
        elif name == 'opencode':
            from llm.providers.opencode import OpenCodeProvider
            return OpenCodeProvider
        else:
            raise ProviderNotFound(f"Unknown provider: {name}")

    def _get_provider(self, name: str = None) -> BaseLLMProvider:
        name = name or self.config.get('llm_provider', 'ollama')
        if name not in self._providers:
            provider_cls = self._get_provider_class(name)
            self._providers[name] = provider_cls(self.config)
        return self._providers[name]

    async def generate(self, messages: list[dict], provider: str = None, **kwargs) -> str:
        p = self._get_provider(provider)
        return await p.generate(messages, **kwargs)

    async def generate_stream(self, messages: list[dict], provider: str = None, **kwargs) -> AsyncGenerator[str, None]:
        p = self._get_provider(provider)
        async for token in p.generate_stream(messages, **kwargs):
            yield token

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], provider: str = None, **kwargs) -> dict:
        p = self._get_provider(provider)
        return await p.generate_with_tools(messages, tools, **kwargs)

    def close(self):
        import asyncio
        for p in self._providers.values():
            if hasattr(p, 'close'):
                try:
                    res = p.close()
                    if asyncio.iscoroutine(res):
                        res.close()
                except Exception:
                    pass

    async def aclose(self):
        import asyncio
        for p in self._providers.values():
            if hasattr(p, 'close'):
                try:
                    res = p.close()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
