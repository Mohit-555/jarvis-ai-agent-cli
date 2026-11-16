import time
from typing import Any

from core.session import Session


class ContextAssembler:
    def __init__(self, system_prompt: str = None):
        self.system_prompt = system_prompt or self._default_system_prompt()

    def _default_system_prompt(self):
        return """You are Jarvis, an advanced AI assistant. You are helpful, harmless, and honest.

Capabilities:
- Answer questions and have conversations
- Use tools to perform actions (web search, file operations, code execution)
- Remember context across conversations
- Execute multi-step tasks

Guidelines:
- Think step by step for complex tasks
- Use tools when needed to provide accurate information
- Be concise and clear in responses
- If you don't know something, say so
- Never execute commands that could harm the system"""

    def assemble(self, session: Session, config: dict = None, extra_context: dict = None) -> list[dict]:
        messages = [{"role": "system", "content": self._build_system_context(config, extra_context)}]
        context_messages = session.get_context(limit=20)
        messages.extend(context_messages)
        return messages

    def _build_system_context(self, config: dict = None, extra: dict = None) -> str:
        parts = [self.system_prompt]
        if config:
            parts.append(f"\nCurrent Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            parts.append(f"Assistant Name: {config.get('assistant_name', 'Jarvis')}")
            parts.append(f"Device: {config.get('device', 'cpu').upper()}")
            if config.get('enable_web_search'):
                parts.append("- Web search: available")
            if config.get('enable_code_exec'):
                parts.append("- Code execution: available")
            if config.get('enable_system_control'):
                parts.append("- System control: available")
        if extra:
            for key, value in extra.items():
                parts.append(f"\n{key}: {value}")
        return "\n".join(parts)

    def update_system_prompt(self, prompt: str):
        self.system_prompt = prompt
