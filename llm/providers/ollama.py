import json
import httpx
from typing import AsyncGenerator

from llm.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    name = 'ollama'

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get('ollama_base_url', 'http://localhost:11434')
        self.model = config.get('ollama_model', 'llama3.2:3b')

    async def generate(self, messages: list[dict], **kwargs) -> str:
        # Keep keys compliant with Ollama /api/chat
        formatted_msgs = []
        for msg in messages:
            formatted_msgs.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })

        payload = {
            'model': kwargs.get('model', self.model),
            'messages': formatted_msgs,
            'stream': False,
            'options': {
                'temperature': kwargs.get('temperature', 0.7),
                'num_predict': kwargs.get('max_tokens', 2048),
            }
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
                resp = await client.post('/api/chat', json=payload)
                resp.raise_for_status()
                data = resp.json()
                message = data.get('message', {})
                return message.get('content', '')
        except httpx.RequestError as e:
            return f"Error communicating with Ollama: {e}"

    async def generate_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        formatted_msgs = []
        for msg in messages:
            formatted_msgs.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', '')
            })

        payload = {
            'model': kwargs.get('model', self.model),
            'messages': formatted_msgs,
            'stream': True,
            'options': {
                'temperature': kwargs.get('temperature', 0.7),
                'num_predict': kwargs.get('max_tokens', 2048),
            }
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
                async with client.stream('POST', '/api/chat', json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                message = data.get('message', {})
                                token = message.get('content', '')
                                if token:
                                    yield token
                                if data.get('done'):
                                    break
                            except json.JSONDecodeError:
                                continue
        except httpx.RequestError as e:
            yield f"Error: {e}"

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        updated_messages = [dict(m) for m in messages]
        if tools:
            tool_descriptions = "\n".join([
                f"- {t['function']['name']}: {t['function']['description']}"
                for t in tools
            ])
            instruction = f"\n\nAvailable tools:\n{tool_descriptions}\n\nRespond with tool calls in JSON format: {{\"tool\": \"name\", \"arguments\": {{...}}}}"
            if updated_messages:
                updated_messages[-1]['content'] = updated_messages[-1].get('content', '') + instruction
            else:
                updated_messages.append({'role': 'user', 'content': instruction})

        content = await self.generate(messages=updated_messages, **kwargs)

        try:
            tool_call = json.loads(content)
            if 'tool' in tool_call:
                return {
                    'content': None,
                    'tool_calls': [{
                        'function': {
                            'name': tool_call['tool'],
                            'arguments': json.dumps(tool_call.get('arguments', {}))
                        }
                    }]
                }
        except json.JSONDecodeError:
            pass

        return {'content': content, 'tool_calls': None}

    async def close(self):
        pass
