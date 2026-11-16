import logging
from abc import ABC, abstractmethod

logger = logging.getLogger('jarvis.plugins.base')


class JarvisPlugin(ABC):
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tools: list[dict] = []

    @abstractmethod
    def setup(self, config: dict = None):
        pass

    @abstractmethod
    def teardown(self):
        pass

    def health_check(self) -> dict:
        return {"name": self.name, "status": "ok", "version": self.version}
