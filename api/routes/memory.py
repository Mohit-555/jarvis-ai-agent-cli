import logging

logger = logging.getLogger('jarvis.api.memory')

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

    class StoreFactRequest(BaseModel):
        content: str
        tags: list[str] = []
        source: str = "api"

    class QueryRequest(BaseModel):
        query: str
        limit: int = 10

    @router.get("/memory")
    async def query_memory(query: str = "", limit: int = 10):
        try:
            from memory.store import MemoryStore
            store = MemoryStore()
            results = store.search(query, limit=limit)
            return {"results": results, "count": len(results)}
        except ImportError:
            raise HTTPException(status_code=501, detail="Memory store not available")
        except Exception as e:
            logger.error(f"Memory query error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/memory")
    async def store_memory(req: StoreFactRequest):
        try:
            from memory.store import MemoryStore
            store = MemoryStore()
            entry = store.add(req.content, tags=req.tags, source=req.source)
            return {"id": str(entry.id), "status": "stored"}
        except ImportError:
            raise HTTPException(status_code=501, detail="Memory store not available")
        except Exception as e:
            logger.error(f"Memory store error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete("/memory/{memory_id}")
    async def delete_memory(memory_id: str):
        try:
            from memory.store import MemoryStore
            store = MemoryStore()
            store.delete(memory_id)
            return {"id": memory_id, "status": "deleted"}
        except ImportError:
            raise HTTPException(status_code=501, detail="Memory store not available")
        except Exception as e:
            logger.error(f"Memory delete error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
else:
    router = None
