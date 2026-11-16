import asyncio
import json
import logging
import shutil

logger = logging.getLogger('jarvis.mcp.client')

HAS_ANYIO = False
HAS_HTTPX = False
HAS_MCP = False

try:
    import anyio
    HAS_ANYIO = True
except ImportError:
    pass

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    pass

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    try:
        from mcp import ClientSession
        HAS_MCP = True
    except ImportError:
        pass


class MCPClient:
    def __init__(self):
        self._session = None
        self._exit_stack = None
        self._read_stream = None
        self._write_stream = None
        self._process = None
        self._connected = False

    async def connect(self, server_config: dict) -> bool:
        transport = server_config.get("transport", "stdio")
        if transport == "stdio":
            return await self._connect_stdio(server_config)
        elif transport == "sse":
            return await self._connect_sse(server_config)
        else:
            logger.error(f"Unsupported transport: {transport}")
            return False

    async def _connect_stdio(self, config: dict) -> bool:
        if not HAS_MCP:
            logger.warning("MCP SDK not installed, using mock mode")
            self._connected = True
            return True
        if not HAS_ANYIO:
            logger.warning("anyio not installed, cannot connect MCP stdio")
            return False
        command = shutil.which(config.get("command", ""))
        if not command:
            logger.error(f"MCP command not found: {config.get('command')}")
            return False
        try:
            server_params = StdioServerParameters(
                command=command,
                args=config.get("args", []),
                env=config.get("env"),
            )
            self._exit_stack = anyio.ExitStack()
            streams = await self._exit_stack.enter_async_context(stdio_client(server_params))
            self._read_stream, self._write_stream = streams
            self._session = await self._exit_stack.enter_async_context(ClientSession(self._read_stream, self._write_stream))
            await self._session.initialize()
            self._connected = True
            logger.info(f"Connected to MCP server: {config.get('command')}")
            return True
        except Exception as e:
            logger.error(f"MCP stdio connect failed: {e}")
            return False

    async def _connect_sse(self, config: dict) -> bool:
        if not HAS_HTTPX:
            logger.warning("httpx not installed, cannot use SSE transport")
            return False
        url = config.get("url", "")
        if not url:
            logger.error("SSE transport requires 'url' in config")
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    self._connected = True
                    logger.info(f"Connected to MCP SSE: {url}")
                    return True
                logger.error(f"SSE connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"MCP SSE connect failed: {e}")
            return False

    async def list_tools(self) -> list[dict]:
        if not self._connected:
            return []
        if not HAS_MCP or not self._session:
            return [{"name": "mock_tool", "description": "Mock MCP tool", "parameters": {}}]
        try:
            tools = await self._session.list_tools()
            return [{"name": t.name, "description": t.description, "parameters": t.inputSchema} for t in tools.tools]
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    async def call_tool(self, name: str, args: dict = None) -> dict:
        if not self._connected:
            return {"error": "Not connected"}
        if not HAS_MCP or not self._session:
            return {"result": f"Mock result for {name}"}
        try:
            result = await self._session.call_tool(name, arguments=args or {})
            return {"result": result.content if hasattr(result, 'content') else str(result)}
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            return {"error": str(e)}

    async def disconnect(self):
        self._connected = False
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._exit_stack = None
        logger.info("MCP client disconnected")
