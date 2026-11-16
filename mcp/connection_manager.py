import asyncio
import logging

logger = logging.getLogger('jarvis.mcp.connection_manager')

try:
    from mcp.client import MCPClient
    HAS_MCP_CLIENT = True
except ImportError:
    HAS_MCP_CLIENT = False
    MCPClient = object


class MCPConnectionManager:
    def __init__(self):
        self._connections: dict[str, MCPClient] = {}
        self._configs: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start_all(self):
        if not HAS_MCP_CLIENT:
            logger.warning("MCP client not available")
            return
        self._running = True
        for name, config in self._configs.items():
            await self._start_one(name, config)

    async def _start_one(self, name: str, config: dict):
        client = MCPClient()
        success = await client.connect(config)
        if success:
            self._connections[name] = client
            logger.info(f"MCP '{name}' connected")
            if config.get("auto_reconnect", True):
                self._tasks[name] = asyncio.create_task(self._reconnect_loop(name, config))
        else:
            logger.error(f"MCP '{name}' failed to connect")

    async def _reconnect_loop(self, name: str, config: dict):
        while self._running:
            await asyncio.sleep(30)
            client = self._connections.get(name)
            if client and client._connected:
                continue
            logger.info(f"Reconnecting MCP '{name}'...")
            await self._start_one(name, config)

    async def stop_all(self):
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
        for name, client in self._connections.items():
            await client.disconnect()
        self._connections.clear()
        self._tasks.clear()
        logger.info("All MCP connections stopped")

    async def restart(self, name: str):
        if name in self._connections:
            await self._connections[name].disconnect()
            del self._connections[name]
        if name in self._tasks:
            self._tasks[name].cancel()
            del self._tasks[name]
        config = self._configs.get(name)
        if config:
            await self._start_one(name, config)

    async def health_check(self) -> dict[str, bool]:
        results = {}
        for name, client in self._connections.items():
            try:
                tools = await client.list_tools()
                results[name] = isinstance(tools, list)
            except Exception:
                results[name] = False
        return results

    def add_server(self, name: str, config: dict):
        self._configs[name] = config

    def remove_server(self, name: str):
        self._configs.pop(name, None)

    def get_client(self, name: str) -> MCPClient | None:
        return self._connections.get(name)
