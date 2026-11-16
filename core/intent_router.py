import re
from typing import Any


INTENT_PATTERNS = {
    'conversation': r'\b(hi|hello|hey|how are you|what\'s up)\b',
    'web_search': r'\b(search|find|look up|google|research|what is|who is)\b.*\b(on the web|online|internet)\b|\b(search|google)\b',
    'code': r'\b(write|create|make|develop|build|implement|fix|debug|refactor)\b.*\b(code|function|class|script|program|app)\b|\b(python|javascript|typescript|code)\b',
    'file_operation': r'\b(read|write|create|delete|move|copy|list|find|search)\b.*\b(file|folder|directory|document)\b',
    'system_control': r'\b(run|execute|launch|open|start|stop|kill)\b.*\b(command|app|process|program|terminal)\b',
    'memory': r'\b(remember|forget|recall|what.*know|memory|remembered)\b',
    'email': r'\b(email|mail|inbox|send.*email|read.*email|compose)\b',
    'github': r'\b(git|github|commit|push|pull|pr|issue|repo)\b',
    'voice': r'\b(voice|speak|say|talk|listen|mic|microphone)\b',
    'help': r'\b(help|commands|what can you do|capabilities)\b',
}


class IntentRouter:
    def __init__(self):
        self._patterns = INTENT_PATTERNS.copy()
        self._custom_routes: dict[str, callable] = {}

    def classify(self, text: str) -> str:
        text = text.lower().strip()
        for intent, pattern in self._patterns.items():
            if re.search(pattern, text):
                return intent
        return 'general'

    def register_pattern(self, intent: str, pattern: str):
        self._patterns[intent] = pattern

    def route(self, text: str, context: dict = None) -> dict[str, Any]:
        intent = self.classify(text)
        return {
            'intent': intent,
            'confidence': 0.8 if intent != 'general' else 0.3,
            'text': text,
            'context': context or {},
        }

    async def route_llm(self, text: str, llm_call: callable) -> dict[str, Any]:
        prompt = f"""Classify the user's intent. Choose ONE: conversation, web_search, code, file_operation, system_control, memory, email, github, voice, help.

User: {text}
Intent:"""
        intent = await llm_call(prompt, max_tokens=20)
        intent = intent.strip().lower()
        if intent not in self._patterns:
            intent = 'general'
        return {'intent': intent, 'text': text}
