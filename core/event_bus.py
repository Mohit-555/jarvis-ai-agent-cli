import asyncio
import logging
from collections import defaultdict
from typing import Callable, Any

logger = logging.getLogger('jarvis.event_bus')


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._async_handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, handler: Callable):
        self._handlers[event].append(handler)
        return handler

    def on_async(self, event: str, handler: Callable):
        self._async_handlers[event].append(handler)
        return handler

    def emit(self, event: str, **data):
        logger.debug(f"Event: {event} {data}")
        for handler in self._handlers.get(event, []):
            try:
                handler(**data)
            except Exception as e:
                logger.error(f"Handler error for {event}: {e}")

    async def emit_async(self, event: str, **data):
        logger.debug(f"Async event: {event} {data}")
        for handler in self._handlers.get(event, []):
            try:
                handler(**data)
            except Exception as e:
                logger.error(f"Handler error for {event}: {e}")
        for handler in self._async_handlers.get(event, []):
            try:
                await handler(**data)
            except Exception as e:
                logger.error(f"Async handler error for {event}: {e}")

    def off(self, event: str, handler: Callable):
        self._handlers[event] = [h for h in self._handlers[event] if h != handler]
        self._async_handlers[event] = [h for h in self._async_handlers[event] if h != handler]

    def clear(self):
        self._handlers.clear()
        self._async_handlers.clear()


EVENTS = {
    'SYSTEM_STARTUP': 'system:startup',
    'SYSTEM_SHUTDOWN': 'system:shutdown',
    'SESSION_CREATED': 'session:created',
    'SESSION_DESTROYED': 'session:destroyed',
    'AGENT_START': 'agent:start',
    'AGENT_STEP': 'agent:step',
    'AGENT_COMPLETE': 'agent:complete',
    'AGENT_ERROR': 'agent:error',
    'TOOL_CALL': 'tool:call',
    'TOOL_RESULT': 'tool:result',
    'TOOL_ERROR': 'tool:error',
    'LLM_CALL': 'llm:call',
    'LLM_RESPONSE': 'llm:response',
    'MEMORY_WRITE': 'memory:write',
    'MEMORY_READ': 'memory:read',
    'VOICE_INPUT': 'voice:input',
    'VOICE_OUTPUT': 'voice:output',
    'SCHEDULER_TICK': 'scheduler:tick',
    'ERROR': 'system:error',
}

event_bus = EventBus()
