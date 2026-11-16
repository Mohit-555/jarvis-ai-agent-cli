from openai import AsyncOpenAI
from httpx import Timeout as HTTPXTimeout
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider

REQUEST_TIMEOUT = 120.0


class OpenCodeProvider(BaseLLMProvider):
    name = 'opencode'

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = AsyncOpenAI(
            base_url="https://opencode.ai/zen/v1",
            api_key=config.get('opencode_api_key') or '',
            timeout=HTTPXTimeout(REQUEST_TIMEOUT),
        )
        self.model = config.get('opencode_model', 'deepseek-v4-flash-free').removeprefix('opencode/')

    async def generate(self, messages: list[dict], **kwargs) -> str:
        resp = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 4096),
            timeout=REQUEST_TIMEOUT,
        )
        return resp.choices[0].message.content or ''

    async def generate_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 4096),
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        resp = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=messages,
            tools=tools if tools else None,
            tool_choice=kwargs.get('tool_choice', 'auto') if tools else None,
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 8192),
            timeout=REQUEST_TIMEOUT,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            return {
                'content': msg.content,
                'tool_calls': [{
                    'id': tc.id,
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments,
                    }
                } for tc in msg.tool_calls]
            }
        return {'content': msg.content or '', 'tool_calls': None}
