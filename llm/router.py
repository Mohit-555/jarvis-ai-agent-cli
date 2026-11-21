import time
import asyncio
from typing import AsyncGenerator

from core.exceptions import ProviderNotFound
from core.logger import central_logger
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

    async def generate(self, messages: list[dict], provider: str = None, timeout: float = 60.0, **kwargs) -> str:
        provider_name = provider or self.config.get('llm_provider', 'ollama')
        model_name = self.config.get(f'{provider_name}_model', 'default')
        p = self._get_provider(provider_name)
        
        last_msg = messages[-1].get("content", "") if messages else ""
        central_logger.log_llm_start(provider_name, model_name, str(last_msg))
        start_t = time.time()
        try:
            res = await asyncio.wait_for(p.generate(messages, **kwargs), timeout=timeout)
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=True)
            return res
        except asyncio.TimeoutError:
            duration = time.time() - start_t
            err = f"LLM generation timed out after {timeout}s"
            central_logger.log_llm_end(provider_name, model_name, duration, success=False, error=err)
            raise TimeoutError(err)
        except Exception as e:
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=False, error=str(e))
            raise

    async def generate_stream(self, messages: list[dict], provider: str = None, **kwargs) -> AsyncGenerator[str, None]:
        provider_name = provider or self.config.get('llm_provider', 'ollama')
        model_name = self.config.get(f'{provider_name}_model', 'default')
        p = self._get_provider(provider_name)
        
        last_msg = messages[-1].get("content", "") if messages else ""
        central_logger.log_llm_start(provider_name, model_name, str(last_msg))
        start_t = time.time()
        token_count = 0
        try:
            async for token in p.generate_stream(messages, **kwargs):
                token_count += 1
                yield token
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=True)
        except Exception as e:
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=False, error=str(e))
            raise

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], provider: str = None, timeout: float = 60.0, **kwargs) -> dict:
        provider_name = provider or self.config.get('llm_provider', 'ollama')
        model_name = self.config.get(f'{provider_name}_model', 'default')
        p = self._get_provider(provider_name)
        
        last_msg = messages[-1].get("content", "") if messages else ""
        central_logger.log_llm_start(provider_name, model_name, f"[with_tools] {str(last_msg)}")
        start_t = time.time()
        try:
            res = await asyncio.wait_for(p.generate_with_tools(messages, tools, **kwargs), timeout=timeout)
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=True)
            return res
        except asyncio.TimeoutError:
            duration = time.time() - start_t
            err = f"LLM generate_with_tools timed out after {timeout}s"
            central_logger.log_llm_end(provider_name, model_name, duration, success=False, error=err)
            raise TimeoutError(err)
        except Exception as e:
            duration = time.time() - start_t
            central_logger.log_llm_end(provider_name, model_name, duration, success=False, error=str(e))
            raise

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
