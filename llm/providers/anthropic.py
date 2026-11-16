from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    name = 'anthropic'

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get('anthropic_api_key', '')
        self.model = config.get('anthropic_model', 'claude-3-haiku-20240307')
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system = ''
        converted = []
        for msg in messages:
            if msg['role'] == 'system':
                system = msg['content']
            else:
                converted.append({'role': msg['role'], 'content': msg['content']})
        return system, converted

    async def generate(self, messages: list[dict], **kwargs) -> str:
        system, msgs = self._convert_messages(messages)
        resp = await self.client.messages.create(
            model=kwargs.get('model', self.model),
            messages=msgs,
            system=system or None,
            max_tokens=kwargs.get('max_tokens', 2048),
            temperature=kwargs.get('temperature', 0.7),
        )
        return resp.content[0].text if resp.content else ''

    async def generate_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        system, msgs = self._convert_messages(messages)
        async with self.client.messages.stream(
            model=kwargs.get('model', self.model),
            messages=msgs,
            system=system or None,
            max_tokens=kwargs.get('max_tokens', 2048),
            temperature=kwargs.get('temperature', 0.7),
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        system, msgs = self._convert_messages(messages)
        anthropic_tools = []
        for t in tools:
            anthropic_tools.append({
                'name': t['function']['name'],
                'description': t['function']['description'],
                'input_schema': t['function']['parameters'],
            })
        resp = await self.client.messages.create(
            model=kwargs.get('model', self.model),
            messages=msgs,
            system=system or None,
            tools=anthropic_tools or None,
            max_tokens=kwargs.get('max_tokens', 4096),
            temperature=kwargs.get('temperature', 0.7),
        )
        if resp.stop_reason == 'tool_use':
            tool_calls = []
            for block in resp.content:
                if block.type == 'tool_use':
                    tool_calls.append({
                        'id': block.id,
                        'function': {
                            'name': block.name,
                            'arguments': json.dumps(block.input),
                        }
                    })
            return {'content': None, 'tool_calls': tool_calls}
        text = ''.join(block.text for block in resp.content if block.type == 'text')
        return {'content': text, 'tool_calls': None}
