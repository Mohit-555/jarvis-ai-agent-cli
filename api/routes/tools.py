import logging

logger = logging.getLogger('jarvis.api.tools')

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    APIRouter = object
    BaseModel = object

if HAS_FASTAPI:
    router = APIRouter()

    class CallToolRequest(BaseModel):
        tool: str
        args: dict = {}

    @router.get("/tools")
    async def list_tools():
        try:
            from tools.registry import ToolRegistry
            registry = ToolRegistry()
            tools = registry.list_tools()
            return {"tools": tools, "count": len(tools)}
        except ImportError:
            raise HTTPException(status_code=501, detail="Tool registry not available")
        except Exception as e:
            logger.error(f"List tools error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/tools/call")
    async def call_tool(req: CallToolRequest):
        try:
            from tools.registry import ToolRegistry
            registry = ToolRegistry()
            result = registry.execute(req.tool, **req.args)
            return {"tool": req.tool, "result": result, "status": "success"}
        except ImportError:
            raise HTTPException(status_code=501, detail="Tool registry not available")
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
else:
    router = None
