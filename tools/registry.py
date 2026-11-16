from typing import Any, Callable
from core.event_bus import event_bus


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, tool: dict):
        name = tool["name"]
        self._tools[name] = tool
        event_bus.emit("tool:registered", name=name)

    def get(self, name: str) -> dict | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [
            {"name": t["name"], "description": t.get("description", "")}
            for t in self._tools.values()
        ]

    def call(self, name: str, **kwargs) -> Any:
        tool = self.get(name)
        if not tool:
            raise KeyError(f"Tool not found: {name}")
        event_bus.emit("tool:call", name=name, args=kwargs)
        try:
            handler = tool["handler"]
            result = handler(**kwargs)
            event_bus.emit("tool:result", name=name, result=result)
            return result
        except Exception as e:
            event_bus.emit("tool:error", name=name, error=str(e))
            raise
