from typing import AsyncGenerator
import json

from llm.providers.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    name = 'gemini'

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get('gemini_api_key', '')
        self.model = config.get('gemini_model', 'gemini-2.0-flash')
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("The 'google-generativeai' package is required for Gemini provider. Run: pip install google-generativeai")
            genai.configure(api_key=self.api_key)
            self._client = genai
        return self._client

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system = ''
        history = []
        for msg in messages:
            if msg['role'] == 'system':
                system = msg['content']
            elif msg['role'] in ('user', 'assistant'):
                role = 'model' if msg['role'] == 'assistant' else 'user'
                history.append({'role': role, 'parts': [msg['content']]})
        return system, history

    async def generate(self, messages: list[dict], **kwargs) -> str:
        system, history = self._convert_messages(messages)
        model = self.client.GenerativeModel(
            model_name=kwargs.get('model', self.model),
            system_instruction=system or None,
        )
        chat = model.start_chat(history=history[:-1] if history else [])
        last_msg = history[-1]['parts'][0] if history else ''
        resp = await chat.send_message_async(last_msg)
        return resp.text

    async def generate_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        system, history = self._convert_messages(messages)
        model = self.client.GenerativeModel(
            model_name=kwargs.get('model', self.model),
            system_instruction=system or None,
        )
        chat = model.start_chat(history=history[:-1] if history else [])
        last_msg = history[-1]['parts'][0] if history else ''
        resp = await chat.send_message_async(last_msg, stream=True)
        async for chunk in resp:
            if chunk.text:
                yield chunk.text

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict:
        system, history = self._convert_messages(messages)
        gemini_tools = []
        for t in tools:
            gemini_tools.append({
                'function_declarations': [{
                    'name': t['function']['name'],
                    'description': t['function']['description'],
                    'parameters': t['function']['parameters'],
                }]
            })
        model = self.client.GenerativeModel(
            model_name=kwargs.get('model', self.model),
            system_instruction=system or None,
            tools=gemini_tools or None,
        )
        chat = model.start_chat(history=history[:-1] if history else [])
        last_msg = history[-1]['parts'][0] if history else ''
        resp = await chat.send_message_async(last_msg)
        if resp.candidates and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if part.function_call:
                    return {
                        'content': None,
                        'tool_calls': [{
                            'function': {
                                'name': part.function_call.name,
                                'arguments': json.dumps(dict(part.function_call.args)),
                            }
                        }]
                    }
        return {'content': resp.text, 'tool_calls': None}
