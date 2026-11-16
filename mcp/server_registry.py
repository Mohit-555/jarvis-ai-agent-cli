import json
import logging

logger = logging.getLogger('jarvis.mcp.registry')

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class MCPServerRegistry:
    def __init__(self):
        self._servers: dict[str, dict] = {}

    def register(self, name: str, config: dict):
        if not config.get("command") and not config.get("url"):
            raise ValueError(f"MCP server '{name}' must have 'command' or 'url'")
        self._servers[name] = {
            "name": name,
            "command": config.get("command", ""),
            "args": config.get("args", []),
            "url": config.get("url", ""),
            "transport": config.get("transport", "stdio"),
            "enabled": config.get("enabled", True),
            "env": config.get("env", {}),
        }
        logger.info(f"Registered MCP server: {name}")

    def unregister(self, name: str):
        self._servers.pop(name, None)
        logger.info(f"Unregistered MCP server: {name}")

    def get(self, name: str) -> dict | None:
        return self._servers.get(name)

    def list_servers(self) -> list[dict]:
        return list(self._servers.values())

    def list_enabled(self) -> list[dict]:
        return [s for s in self._servers.values() if s.get("enabled")]

    def load_from_config(self, path: str):
        import os
        if not os.path.exists(path):
            logger.warning(f"MCP config not found: {path}")
            return
        try:
            if path.endswith((".yaml", ".yml")) and HAS_YAML:
                with open(path) as f:
                    config = yaml.safe_load(f) or {}
            else:
                with open(path) as f:
                    config = json.load(f)
            servers = config.get("mcp_servers", config.get("servers", {}))
            for name, cfg in servers.items():
                self.register(name, cfg)
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
