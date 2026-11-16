from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseLLMProvider(ABC):
    name: str = 'base'

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def generate(self, messages: list[dict], **kwargs) -> str: ...

    @abstractmethod
    async def generate_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def generate_with_tools(self, messages: list[dict], tools: list[dict], **kwargs) -> dict: ...
