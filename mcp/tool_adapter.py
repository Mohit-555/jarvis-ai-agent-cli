import logging

logger = logging.getLogger('jarvis.mcp.adapter')


class MCPToolAdapter:
    @staticmethod
    def adapt(mcp_tool: dict) -> dict:
        return {
            "name": mcp_tool.get("name", ""),
            "description": mcp_tool.get("description", ""),
            "parameters": mcp_tool.get("parameters", mcp_tool.get("inputSchema", {})),
            "source": "mcp",
            "input_schema": mcp_tool.get("inputSchema", mcp_tool.get("parameters", {})),
        }

    @staticmethod
    def adapt_all(tools: list[dict]) -> list[dict]:
        return [MCPToolAdapter.adapt(t) for t in tools]

    @staticmethod
    def to_mcp_format(internal_tool: dict) -> dict:
        return {
            "name": internal_tool.get("name", ""),
            "description": internal_tool.get("description", ""),
            "inputSchema": internal_tool.get("parameters", internal_tool.get("input_schema", {})),
        }

    @staticmethod
    def to_internal_call(mcp_name: str, mcp_args: dict) -> dict:
        return {
            "tool": mcp_name,
            "arguments": mcp_args,
        }
